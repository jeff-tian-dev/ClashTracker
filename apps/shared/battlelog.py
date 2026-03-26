"""Battle-log cursor utilities shared between ingestion modules.

Used by both ``player_activity`` (general multiplayer battle logs) and
``legends`` (Legends League battle logs) to track the last-seen battle
and detect new entries across ingestion runs.
"""

from __future__ import annotations


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
        "battleType": b.get("battleType") or "",
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
