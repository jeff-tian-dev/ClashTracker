"""Train the XGBoost clan war outcome model from ended wars in Supabase.

Usage (repo root, with .env.local present):

    pip install -r apps/api/requirements.txt
    python scripts/train_war_outcome.py [--out PATH] [--min-wars 30]

Writes ``WAR_OUTCOME_MODEL_PATH`` (default ``apps/shared/models/war_outcome_xgb.json``);
``.\\deploy.ps1`` ships it to the VM with the rest of ``apps/shared``. Features come
from ``shared.war_outcome`` so training and API inference cannot drift apart.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_apps_root = Path(__file__).resolve().parent.parent / "apps"
if str(_apps_root) not in sys.path:
    sys.path.insert(0, str(_apps_root))

from shared.logutil import configure_logging  # noqa: E402

configure_logging("training")

import numpy as np  # noqa: E402
import xgboost as xgb  # noqa: E402

from ingestion.db import get_db  # noqa: E402
from shared.config import WAR_OUTCOME_MODEL_PATH  # noqa: E402
from shared.war_outcome import (  # noqa: E402
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    HISTORY_WINDOW,
    features_to_row,
    label_for_war,
    training_snapshots,
)

logger = logging.getLogger("training.war_outcome")

_PAGE = 1000
_WAR_ID_CHUNK = 50
_VALIDATION_SHARE = 0.2

XGB_PARAMS: dict[str, Any] = {
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "max_depth": 4,
    "eta": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 2,
}


def _fetch_all(make_query: Callable[[], Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = make_query().range(offset, offset + _PAGE - 1).execute().data or []
        rows.extend(page)
        if len(page) < _PAGE:
            return rows
        offset += _PAGE


def load_ended_wars() -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    db = get_db()
    wars = _fetch_all(
        lambda: db.table("wars")
        .select("id,clan_tag,team_size,attacks_per_member,start_time,clan_stars,result")
        .eq("state", "warEnded")
        .order("start_time")
    )
    attacks: dict[int, list[dict[str, Any]]] = defaultdict(list)
    ids = [w["id"] for w in wars]
    for i in range(0, len(ids), _WAR_ID_CHUNK):
        chunk = ids[i : i + _WAR_ID_CHUNK]
        for a in _fetch_all(
            lambda: db.table("war_attacks")
            .select("war_id,defender_tag,stars,destruction_percentage,attack_order,is_home_attacker")
            .in_("war_id", chunk)
            .order("id")
        ):
            attacks[a["war_id"]].append(a)
    return wars, attacks


def build_dataset(
    wars: list[dict[str, Any]], attacks: dict[int, list[dict[str, Any]]]
) -> tuple[list[list[list[float]]], list[int]]:
    """Per-war groups of snapshot rows + labels; wars must be sorted by start_time ascending."""
    groups: list[list[list[float]]] = []
    labels: list[int] = []
    prior_by_clan: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for war in wars:
        label = label_for_war(war)
        war_attacks = attacks.get(war["id"], [])
        history = prior_by_clan[war["clan_tag"]][-HISTORY_WINDOW:][::-1]  # newest first
        if label is not None and war_attacks:
            groups.append([features_to_row(f) for f in training_snapshots(war, war_attacks, history)])
            labels.append(label)
        prior_by_clan[war["clan_tag"]].append(war)
    return groups, labels


def _matrix(groups: list[list[list[float]]], labels: list[int]) -> xgb.DMatrix:
    x = [row for g in groups for row in g]
    y = [lab for g, lab in zip(groups, labels) for _ in g]
    return xgb.DMatrix(
        np.asarray(x, dtype=np.float32),
        label=np.asarray(y, dtype=np.float32),
        feature_names=list(FEATURE_NAMES),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=WAR_OUTCOME_MODEL_PATH)
    parser.add_argument("--min-wars", type=int, default=30)
    parser.add_argument("--rounds", type=int, default=400)
    args = parser.parse_args()

    wars, attacks = load_ended_wars()
    groups, labels = build_dataset(wars, attacks)
    logger.info(
        "war outcome dataset built",
        extra={"event": "ml.war_outcome.train.dataset", "wars": len(groups), "rows": sum(map(len, groups))},
    )
    if len(groups) < args.min_wars:
        logger.error(
            "not enough ended wars to train",
            extra={"event": "ml.war_outcome.train.insufficient_data", "wars": len(groups), "min_wars": args.min_wars},
        )
        return 1

    # Time-based split by war (not by snapshot) so validation wars are unseen and newest.
    split = int(len(groups) * (1 - _VALIDATION_SHARE))
    dtrain = _matrix(groups[:split], labels[:split])
    dvalid = _matrix(groups[split:], labels[split:])

    booster = xgb.train(
        XGB_PARAMS,
        dtrain,
        num_boost_round=args.rounds,
        evals=[(dtrain, "train"), (dvalid, "valid")],
        early_stopping_rounds=30,
        verbose_eval=False,
    )
    best_iteration, best_logloss = booster.best_iteration, booster.best_score
    # Drop trees past the early-stopping point so API inference uses exactly the best model.
    booster = booster[: best_iteration + 1]
    preds = booster.predict(dvalid)
    accuracy = float(((preds >= 0.5) == (dvalid.get_label() >= 0.5)).mean())

    trained_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    booster.set_attr(
        model_version=f"v{FEATURE_SCHEMA_VERSION}-{trained_at[:10]}",
        trained_at=trained_at,
        feature_schema_version=str(FEATURE_SCHEMA_VERSION),
        train_wars=str(split),
        valid_wars=str(len(groups) - split),
        valid_accuracy=f"{accuracy:.4f}",
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(args.out))
    logger.info(
        "war outcome model saved",
        extra={
            "event": "ml.war_outcome.train.complete",
            "path": str(args.out),
            "best_iteration": best_iteration,
            "valid_logloss": best_logloss,
            "valid_accuracy": round(accuracy, 4),
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
