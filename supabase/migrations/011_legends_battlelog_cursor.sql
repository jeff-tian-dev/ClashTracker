-- Per-player cursor for legend-type battle log entries (baseline, no backfill; see ingestion/legends.py).

CREATE TABLE IF NOT EXISTS legends_battlelog_cursor (
    player_tag      TEXT PRIMARY KEY REFERENCES players(tag) ON DELETE CASCADE,
    cursor_snapshot JSONB        NOT NULL,
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
