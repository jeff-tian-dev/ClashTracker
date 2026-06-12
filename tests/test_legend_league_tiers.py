"""Unit tests for Legend League tier id mapping."""

from __future__ import annotations

from shared.legends_roster import (
    legend_league_display_name,
    legend_league_tier_number,
    league_name_is_legends,
    player_in_legend_league,
    player_in_legends_tab,
)
from shared.player_ingest import player_row_from_coc


def test_legend_league_tier_number_maps_ids():
    assert legend_league_tier_number(105000036) == 1
    assert legend_league_tier_number(105000035) == 2
    assert legend_league_tier_number(105000034) == 3
    assert legend_league_tier_number(999) is None


def test_player_in_legend_league_by_tier_id():
    assert player_in_legend_league({"league_tier_id": 105000034, "league_name": "Legend League"})
    assert player_in_legend_league({"league_tier_id": 105000036, "league_name": "Legend League"})
    assert not player_in_legend_league({"league_tier_id": 123, "league_name": "Gold League I"})


def test_player_in_legends_tab_tier_1_only():
    assert player_in_legends_tab({"league_tier_id": 105000036, "league_name": "Legend League 1"})
    assert player_in_legends_tab({"league_name": "Legend League"})
    assert not player_in_legends_tab({"league_tier_id": 105000035, "league_name": "Legend League 2"})
    assert not player_in_legends_tab({"league_tier_id": 105000034, "league_name": "Legend League 3"})
    assert not player_in_legends_tab({"league_name": "Legend League 2"})


def test_league_name_is_legends_accepts_enriched_names():
    assert league_name_is_legends("Legend League")
    assert league_name_is_legends("Legend League 2")
    assert not league_name_is_legends("Gold League I")


def test_legend_league_display_name():
    assert legend_league_display_name(105000035) == "Legend League 2"
    assert legend_league_display_name(None, "Legend League") == "Legend League"


def test_player_row_from_coc_stores_tier_id_and_display_name():
    row = player_row_from_coc(
        {
            "tag": "#ABC",
            "name": "Player",
            "leagueTier": {"id": 105000036, "name": "Legend League"},
        }
    )
    assert row["league_tier_id"] == 105000036
    assert row["league_name"] == "Legend League 1"
