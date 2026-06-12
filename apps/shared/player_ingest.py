"""CoC player payload → DB row mapping and change detection for ingestion."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from shared.legends_roster import legend_league_display_name

# Fields persisted by upsert_player (excluding updated_at and roster columns).
PLAYER_COMPARE_KEYS: tuple[str, ...] = (
    "tag",
    "name",
    "clan_tag",
    "town_hall_level",
    "exp_level",
    "trophies",
    "best_trophies",
    "war_stars",
    "attack_wins",
    "defense_wins",
    "role",
    "war_preference",
    "clan_capital_contributions",
    "league_name",
    "league_tier_id",
)

_PLAYER_ROLE_DISPLAY: dict[str, str] = {
    "member": "Member",
    "admin": "Elder",
    "elder": "Elder",
    "coLeader": "Co-leader",
    "leader": "Leader",
}


def normalize_player_role(role: str | None) -> str | None:
    if not role:
        return None
    return _PLAYER_ROLE_DISPLAY.get(role, role)


def player_row_from_coc(player_data: dict) -> dict:
    """Build the players-table row dict from a CoC GET /players response."""
    clan = player_data.get("clan")
    league_tier = player_data.get("leagueTier") or {}
    league_obj = player_data.get("league") or {}
    raw_league_name = league_tier.get("name") or league_obj.get("name")
    league_tier_id = league_tier.get("id")
    league_name = legend_league_display_name(league_tier_id, raw_league_name) or raw_league_name
    return {
        "tag": player_data["tag"],
        "name": player_data["name"],
        "clan_tag": clan["tag"] if isinstance(clan, dict) else None,
        "town_hall_level": player_data.get("townHallLevel", 1),
        "exp_level": player_data.get("expLevel", 1),
        "trophies": player_data.get("trophies", 0),
        "best_trophies": player_data.get("bestTrophies", 0),
        "war_stars": player_data.get("warStars", 0),
        "attack_wins": player_data.get("attackWins", 0),
        "defense_wins": player_data.get("defenseWins", 0),
        "role": normalize_player_role(player_data.get("role")),
        "war_preference": player_data.get("warPreference"),
        "clan_capital_contributions": player_data.get("clanCapitalContributions", 0),
        "league_name": league_name,
        "league_tier_id": league_tier_id,
    }


def player_row_compare_slice(row: dict) -> dict[str, Any]:
    """Normalize a row dict to the subset used for upsert skip detection."""
    out: dict[str, Any] = {}
    for key in PLAYER_COMPARE_KEYS:
        val = row.get(key)
        if key == "war_preference" and val is None:
            out[key] = None
        elif key in ("town_hall_level", "exp_level", "trophies", "best_trophies", "war_stars", "attack_wins", "defense_wins", "clan_capital_contributions", "league_tier_id"):
            out[key] = int(val) if val is not None else None
        else:
            out[key] = val
    return out


def player_ingest_fingerprint(row: dict) -> str:
    """Stable hash of comparable player fields (for logging/tests)."""
    payload = json.dumps(player_row_compare_slice(row), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def player_rows_unchanged(existing: dict | None, candidate: dict) -> bool:
    if existing is None:
        return False
    return player_row_compare_slice(existing) == player_row_compare_slice(candidate)
