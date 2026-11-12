"""War outcome prediction: shared feature engineering, model loading, and API route."""

from __future__ import annotations

from typing import Any

import pytest

from shared import war_outcome
from shared.war_outcome import (
    FEATURE_NAMES,
    WarOutcomeModel,
    WarOutcomeModelUnavailable,
    WarOutcomePrediction,
    build_war_features,
    features_to_row,
    label_for_war,
    training_snapshots,
)

WAR = {
    "id": 7,
    "clan_tag": "#CLAN",
    "state": "inWar",
    "team_size": 2,
    "attacks_per_member": 2,
    "start_time": "2026-11-10T12:00:00+00:00",
    "result": None,
}


def _atk(order: int, home: bool | None, defender: str, stars: int, destr: float) -> dict[str, Any]:
    return {
        "attack_order": order,
        "is_home_attacker": home,
        "defender_tag": defender,
        "stars": stars,
        "destruction_percentage": destr,
    }


ATTACKS = [
    _atk(1, True, "#O1", 2, 70.0),
    _atk(2, False, "#H1", 3, 100.0),
    _atk(3, True, "#O1", 3, 100.0),  # cleanup on same base: only best counts
    _atk(4, True, "#O2", 1, 40.0),
    _atk(5, None, "#O2", 3, 100.0),  # legacy row: unattributable, ignored
]


def test_features_count_best_attack_per_defender():
    f = build_war_features(WAR, ATTACKS, history=[])
    assert f["clan_stars"] == 4  # 3 on #O1 + 1 on #O2
    assert f["clan_destruction_pct"] == pytest.approx(70.0)  # (100 + 40) / 2
    assert f["opponent_stars"] == 3
    assert f["star_diff"] == 1
    assert f["clan_attacks_used"] == 3
    assert f["clan_avg_stars_per_attack"] == pytest.approx(2.0)
    assert f["progress"] == pytest.approx(4 / 8)
    assert set(f) == set(FEATURE_NAMES)


def test_features_respect_attack_order_cutoff():
    f = build_war_features(WAR, ATTACKS, history=[], max_attack_order=2)
    assert f["clan_stars"] == 2
    assert f["opponent_stars"] == 3
    assert f["clan_attacks_used"] == 1


def test_history_features_neutral_when_empty_and_computed_otherwise():
    empty = build_war_features(WAR, [], history=[])
    assert (empty["hist_wars"], empty["hist_win_rate"]) == (0, 0.5)

    history = [
        {"result": "win", "clan_stars": 6, "team_size": 2},
        {"result": "lose", "clan_stars": 3, "team_size": 2},
    ]
    f = build_war_features(WAR, [], history=history)
    assert f["hist_wars"] == 2
    assert f["hist_win_rate"] == pytest.approx(0.5)
    assert f["hist_avg_star_share"] == pytest.approx((1.0 + 0.5) / 2)


def test_training_snapshots_start_pre_war_and_follow_schema():
    rows = training_snapshots(WAR, ATTACKS, history=[])
    assert len(rows) == len(war_outcome.TRAINING_SNAPSHOT_FRACTIONS)
    assert rows[0]["clan_attacks_used"] == 0 and rows[0]["opponent_attacks_used"] == 0
    assert len(features_to_row(rows[-1])) == len(FEATURE_NAMES)


@pytest.mark.parametrize("result,label", [("win", 1), ("lose", 0), ("tie", 0), (None, None)])
def test_label_for_war(result, label):
    assert label_for_war({"result": result}) == label


def test_load_missing_model_file_is_unavailable(tmp_path):
    with pytest.raises(WarOutcomeModelUnavailable):
        WarOutcomeModel.load(tmp_path / "nope.json")


# ── Real xgboost round trip (skipped when xgboost is not installed) ──


def _tiny_booster(feature_names: list[str]):
    np = pytest.importorskip("numpy")
    xgb = pytest.importorskip("xgboost")
    rng = np.random.default_rng(0)
    x = rng.random((40, len(feature_names)), dtype=np.float32)
    y = (x[:, 0] > 0.5).astype(np.float32)
    booster = xgb.train(
        {"objective": "binary:logistic"},
        xgb.DMatrix(x, label=y, feature_names=feature_names),
        num_boost_round=3,
    )
    booster.set_attr(model_version="test-v1", feature_schema_version=str(war_outcome.FEATURE_SCHEMA_VERSION))
    return booster


def test_xgboost_model_round_trip(tmp_path):
    path = tmp_path / "model.json"
    _tiny_booster(list(FEATURE_NAMES)).save_model(str(path))

    model = WarOutcomeModel.load(path)
    pred = model.predict(build_war_features(WAR, ATTACKS, history=[]))
    assert 0.0 <= pred.win_probability <= 1.0
    assert pred.model_version == "test-v1"


def test_xgboost_model_with_wrong_features_is_rejected(tmp_path):
    path = tmp_path / "model.json"
    _tiny_booster([f"f{i}" for i in range(len(FEATURE_NAMES))]).save_model(str(path))
    with pytest.raises(WarOutcomeModelUnavailable, match="feature names"):
        WarOutcomeModel.load(path)


# ── API route ────────────────────────────────────────────────────────


class _Query:
    def __init__(self, data: Any, single_data: Any = None) -> None:
        self._data = data
        self._single_data = single_data
        self._single = False

    def __getattr__(self, _name):  # select / eq / neq / lt / order / limit
        return lambda *a, **k: self

    def single(self):
        self._single = True
        return self

    def execute(self):
        return type("R", (), {"data": self._single_data if self._single else self._data})()


class _PredictionDb:
    def __init__(self, history: list[dict[str, Any]]) -> None:
        self.history = history

    def table(self, name: str):
        if name == "wars":
            return _Query(self.history, single_data=dict(WAR))
        return _Query(ATTACKS)


class _StubModel:
    def predict(self, features: dict[str, float]) -> WarOutcomePrediction:
        assert set(features) == set(FEATURE_NAMES)
        return WarOutcomePrediction(win_probability=0.73, model_version="stub", trained_at=None)


def test_prediction_route_returns_probability(client, monkeypatch):
    monkeypatch.setattr("api.routers.wars.get_db", lambda: _PredictionDb([]))
    monkeypatch.setattr("api.routers.wars.get_war_outcome_model", lambda: _StubModel())

    r = client.get("/api/wars/7/prediction")
    assert r.status_code == 200
    body = r.json()
    assert body["win_probability"] == pytest.approx(0.73)
    assert body["predicted_result"] == "win"
    assert body["model_version"] == "stub"
    assert body["features"]["clan_stars"] == 4


def test_prediction_route_503_when_model_missing(client, monkeypatch):
    def _missing():
        raise WarOutcomeModelUnavailable("no file")

    monkeypatch.setattr("api.routers.wars.get_db", lambda: _PredictionDb([]))
    monkeypatch.setattr("api.routers.wars.get_war_outcome_model", _missing)

    r = client.get("/api/wars/7/prediction")
    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "model_unavailable"
