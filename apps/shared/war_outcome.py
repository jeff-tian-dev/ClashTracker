"""Clan war outcome prediction: feature engineering + XGBoost model loading.

Feature building is pure (no DB, no xgboost import) and is shared by:

* API inference  → ``GET /api/wars/{war_id}/prediction`` (``api/routers/wars.py``)
* Offline training → ``scripts/train_war_outcome.py``

Training and inference MUST both build features through this module so the
model always sees identically shaped inputs. Bump ``FEATURE_SCHEMA_VERSION``
whenever ``FEATURE_NAMES`` or the meaning of a feature changes, then retrain.

Label: ``1`` = clan won, ``0`` = lose or tie (binary classifier → P(win)).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from .config import WAR_OUTCOME_MODEL_PATH

logger = logging.getLogger(__name__)

FEATURE_SCHEMA_VERSION = 1

# Prior ended wars of the same clan used for the hist_* features.
HISTORY_WINDOW = 20

# Order matters: this is the column order of the training matrix.
FEATURE_NAMES: tuple[str, ...] = (
    "team_size",
    "attacks_per_member",
    "progress",  # share of all attack slots (both sides) used so far, 0..1
    "clan_stars",
    "opponent_stars",
    "star_diff",
    "clan_destruction_pct",
    "opponent_destruction_pct",
    "destruction_diff",
    "clan_attacks_used",
    "opponent_attacks_used",
    "clan_avg_stars_per_attack",
    "opponent_avg_stars_per_attack",
    "hist_wars",
    "hist_win_rate",
    "hist_avg_star_share",  # clan_stars / (team_size * 3), averaged over history
)

# Points in a war (fraction of attacks made) sampled as training rows, so one
# model serves preparation-day (0.0) through late-war predictions.
TRAINING_SNAPSHOT_FRACTIONS: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75)


# ── Feature engineering (pure) ───────────────────────────────────────


def _side_totals(
    attacks: Iterable[dict[str, Any]],
    *,
    home: bool,
    team_size: int,
    max_attack_order: int | None,
) -> tuple[int, float, int, int]:
    """Return (stars, destruction_pct, attacks_used, raw_attack_stars) for one side.

    War stars / destruction count only each defender's *best* attack, matching
    how Clash of Clans scores a war. Rows with ``is_home_attacker`` NULL
    (legacy, pre-migration 014) cannot be attributed and are skipped.
    """
    best_stars: dict[str, int] = {}
    best_destruction: dict[str, float] = {}
    used = 0
    raw_stars = 0
    for a in attacks:
        if a.get("is_home_attacker") is not home:
            continue
        order = int(a.get("attack_order") or 0)
        if max_attack_order is not None and order > max_attack_order:
            continue
        defender = str(a.get("defender_tag") or "")
        stars = int(a.get("stars") or 0)
        destruction = float(a.get("destruction_percentage") or 0.0)
        used += 1
        raw_stars += stars
        best_stars[defender] = max(best_stars.get(defender, 0), stars)
        best_destruction[defender] = max(best_destruction.get(defender, 0.0), destruction)
    destruction_pct = sum(best_destruction.values()) / team_size if team_size > 0 else 0.0
    return sum(best_stars.values()), destruction_pct, used, raw_stars


def _history_features(history: Sequence[dict[str, Any]]) -> tuple[int, float, float]:
    """(count, win_rate, avg_star_share) over prior ended wars; neutral 0.5 when empty."""
    ended = [w for w in history if w.get("result") in ("win", "lose", "tie")][:HISTORY_WINDOW]
    if not ended:
        return 0, 0.5, 0.5
    wins = sum(1 for w in ended if w["result"] == "win")
    shares = [
        int(w.get("clan_stars") or 0) / (int(w["team_size"]) * 3)
        for w in ended
        if w.get("team_size")
    ]
    avg_share = sum(shares) / len(shares) if shares else 0.5
    return len(ended), wins / len(ended), avg_share


def build_war_features(
    war: dict[str, Any],
    attacks: Iterable[dict[str, Any]],
    history: Sequence[dict[str, Any]],
    *,
    max_attack_order: int | None = None,
) -> dict[str, float]:
    """Feature dict for one war as of ``max_attack_order`` (None = all attacks so far).

    ``war`` is a ``wars`` row, ``attacks`` its ``war_attacks`` rows, and
    ``history`` the clan's prior ended ``wars`` rows, newest first. Callers must
    only pass wars that started *before* ``war`` (no leakage).
    """
    attacks = list(attacks)
    team_size = int(war.get("team_size") or 0)
    apm = int(war.get("attacks_per_member") or 0)

    c_stars, c_destr, c_used, c_raw = _side_totals(
        attacks, home=True, team_size=team_size, max_attack_order=max_attack_order
    )
    o_stars, o_destr, o_used, o_raw = _side_totals(
        attacks, home=False, team_size=team_size, max_attack_order=max_attack_order
    )
    total_slots = 2 * team_size * apm
    hist_n, hist_win_rate, hist_share = _history_features(history)

    return {
        "team_size": float(team_size),
        "attacks_per_member": float(apm),
        "progress": min(1.0, (c_used + o_used) / total_slots) if total_slots else 0.0,
        "clan_stars": float(c_stars),
        "opponent_stars": float(o_stars),
        "star_diff": float(c_stars - o_stars),
        "clan_destruction_pct": c_destr,
        "opponent_destruction_pct": o_destr,
        "destruction_diff": c_destr - o_destr,
        "clan_attacks_used": float(c_used),
        "opponent_attacks_used": float(o_used),
        "clan_avg_stars_per_attack": c_raw / c_used if c_used else 0.0,
        "opponent_avg_stars_per_attack": o_raw / o_used if o_used else 0.0,
        "hist_wars": float(hist_n),
        "hist_win_rate": hist_win_rate,
        "hist_avg_star_share": hist_share,
    }


def features_to_row(features: dict[str, float]) -> list[float]:
    """Feature dict → list in ``FEATURE_NAMES`` order (raises KeyError if one is missing)."""
    return [float(features[name]) for name in FEATURE_NAMES]


def label_for_war(war: dict[str, Any]) -> int | None:
    """Training label: 1 win, 0 lose/tie, None if the war has not ended."""
    result = war.get("result")
    if result == "win":
        return 1
    if result in ("lose", "tie"):
        return 0
    return None


def training_snapshots(
    war: dict[str, Any],
    attacks: Sequence[dict[str, Any]],
    history: Sequence[dict[str, Any]],
    fractions: Sequence[float] = TRAINING_SNAPSHOT_FRACTIONS,
) -> list[dict[str, float]]:
    """Feature rows for one ended war at several points in its attack sequence."""
    orders = sorted(
        int(a.get("attack_order") or 0)
        for a in attacks
        if a.get("is_home_attacker") is not None
    )
    rows: list[dict[str, float]] = []
    for frac in fractions:
        n = int(frac * len(orders))
        cutoff = orders[n - 1] if n > 0 else 0
        rows.append(build_war_features(war, attacks, history, max_attack_order=cutoff))
    return rows


# ── Model loading + inference ────────────────────────────────────────


class WarOutcomeModelUnavailable(RuntimeError):
    """Model file missing, xgboost not installed, or feature schema mismatch."""


@dataclass(frozen=True)
class WarOutcomePrediction:
    win_probability: float
    model_version: str | None
    trained_at: str | None


class WarOutcomeModel:
    """Thin wrapper around an ``xgboost.Booster`` trained on ``FEATURE_NAMES``."""

    def __init__(self, booster: Any, path: Path) -> None:
        self._booster = booster
        self.path = path
        self.model_version: str | None = booster.attr("model_version")
        self.trained_at: str | None = booster.attr("trained_at")

    @classmethod
    def load(cls, path: Path) -> WarOutcomeModel:
        if not path.is_file():
            raise WarOutcomeModelUnavailable(f"No war outcome model file at {path}")
        try:
            import xgboost as xgb  # lazy: keeps API startup + tests free of xgboost
        except ImportError as exc:
            raise WarOutcomeModelUnavailable("xgboost is not installed") from exc

        booster = xgb.Booster()
        booster.load_model(str(path))
        names = booster.feature_names
        if names is not None and tuple(names) != FEATURE_NAMES:
            raise WarOutcomeModelUnavailable(
                "Model feature names do not match FEATURE_NAMES; retrain the model."
            )
        schema = booster.attr("feature_schema_version")
        if schema is not None and int(schema) != FEATURE_SCHEMA_VERSION:
            raise WarOutcomeModelUnavailable(
                f"Model feature_schema_version={schema}, code expects {FEATURE_SCHEMA_VERSION}; retrain."
            )
        return cls(booster, path)

    def predict(self, features: dict[str, float]) -> WarOutcomePrediction:
        import numpy as np
        import xgboost as xgb

        matrix = xgb.DMatrix(
            np.asarray([features_to_row(features)], dtype=np.float32),
            feature_names=list(FEATURE_NAMES),
        )
        prob = float(self._booster.predict(matrix)[0])
        return WarOutcomePrediction(
            win_probability=prob,
            model_version=self.model_version,
            trained_at=self.trained_at,
        )


_model_lock = threading.Lock()
_model: WarOutcomeModel | None = None


def get_war_outcome_model() -> WarOutcomeModel:
    """Process-wide cached model. Not cached on failure, so a newly deployed file is picked up."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = WarOutcomeModel.load(WAR_OUTCOME_MODEL_PATH)
                logger.info(
                    "war outcome model loaded",
                    extra={
                        "event": "ml.war_outcome.model.loaded",
                        "path": str(WAR_OUTCOME_MODEL_PATH),
                        "model_version": _model.model_version,
                        "trained_at": _model.trained_at,
                    },
                )
    return _model
