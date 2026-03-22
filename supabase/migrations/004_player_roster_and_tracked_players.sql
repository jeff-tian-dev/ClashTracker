-- Roster reconciliation: who left tracked clans + always-tracked player tags (no FK to players).

ALTER TABLE players
    ADD COLUMN IF NOT EXISTS left_tracked_roster_at TIMESTAMPTZ NULL;

ALTER TABLE players
    ADD COLUMN IF NOT EXISTS roster_sort_bucket SMALLINT GENERATED ALWAYS AS (
        CASE WHEN left_tracked_roster_at IS NULL THEN 0 ELSE 1 END
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_players_roster_sort
    ON players (roster_sort_bucket, left_tracked_roster_at DESC NULLS LAST, name);

CREATE TABLE IF NOT EXISTS tracked_players (
    player_tag TEXT PRIMARY KEY,
    note        TEXT,
    added_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
