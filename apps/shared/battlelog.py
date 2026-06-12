"""Battle-log cursor utilities shared between ingestion modules.

Used by both ``player_activity`` (general multiplayer battle logs) and
``legends`` (Legends League battle logs) to track the last-seen battle
and detect new entries across ingestion runs.
"""

from __future__ import annotations

# CoC renamed Legend League battle logs from ``legend`` to ``ranked`` (2026 league rework).
_LEGEND_BATTLE_TYPES = frozenset({"legend", "ranked"})


def is_legend_league_battle(b: dict) -> bool:
    """True for Legend League entries in a player battle log (``legend`` or ``ranked``)."""
    return (b.get("battleType") or "") in _LEGEND_BATTLE_TYPES


def _normalize_battle_type_for_cursor(bt: str) -> str:
    if bt in _LEGEND_BATTLE_TYPES:
        return "legend"
    return bt


def canonical_snapshot(b: dict) -> dict:
    """Normalize a CoC battle-log entry to a hashable comparison dict."""
    atk = b.get("attackKey")
    if atk is not None:
        attack_bool = bool(atk)
    else:
        attack_bool = bool(b.get("attack", True))
    return {
        "battleTime": b.get("battleTime"),
        "opponentPlayerTag": b.get("opponentPlayerTag") or "",
        "battleType": _normalize_battle_type_for_cursor(b.get("battleType") or ""),
        "attack": attack_bool,
        "stars": int(b.get("stars", 0)),
        "destructionPercentage": int(b.get("destructionPercentage", 0)),
    }


def snapshots_equal(stored: dict, battle: dict) -> bool:
    """True when two battle entries represent the same event."""
    return canonical_snapshot(stored) == canonical_snapshot(battle)


def is_attack(battle: dict) -> bool:
    """True when the battle entry is an attack (not a defense)."""
    if "attackKey" in battle:
        return bool(battle.get("attackKey"))
    return bool(battle.get("attack", True))
