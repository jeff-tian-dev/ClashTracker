-- Display name for always-tracked players (stored at add time).

ALTER TABLE tracked_players
    ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';
