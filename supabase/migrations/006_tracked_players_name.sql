-- Display label for always-tracked players (stored at add time).
-- Renamed to display_name in 007 (see migration 007).

ALTER TABLE tracked_players
    ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';
