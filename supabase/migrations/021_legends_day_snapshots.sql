-- 021_legends_day_snapshots.sql
-- Per-player, per-legends-day trophy snapshot.
--
-- Ingestion upserts one row per Legends-roster player every run. On conflict
-- (same player_tag + legends_day) the row is overwritten, so the LAST snapshot
-- written before the 5:00 UTC daily reset naturally becomes that day's
-- `final_trophies`. The next ingestion run after the reset inserts a NEW row
-- for the new legends_day, leaving the previous day frozen at its final value.
--
-- Used by GET /api/legends when requesting a past legends day: stored
-- `trophies` is the authoritative final_trophies; initial_trophies is derived
-- as final - (attack_total - defense_total) from legends_battles.

CREATE TABLE IF NOT EXISTS legends_day_snapshots (
    player_tag   TEXT NOT NULL REFERENCES players(tag) ON DELETE CASCADE,
    legends_day  DATE NOT NULL,
    trophies     INT NOT NULL,
    snapshot_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (player_tag, legends_day)
);

CREATE INDEX IF NOT EXISTS idx_legends_day_snapshots_day
    ON legends_day_snapshots(legends_day);
