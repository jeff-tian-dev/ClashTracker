-- Per-player battle log cursor (newest battle fingerprint) and attack timestamps for activity charts.

CREATE TABLE IF NOT EXISTS player_battlelog_cursor (
    player_tag      TEXT PRIMARY KEY REFERENCES players(tag) ON DELETE CASCADE,
    cursor_snapshot JSONB        NOT NULL,
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS player_attack_events (
    id          BIGSERIAL PRIMARY KEY,
    player_tag  TEXT        NOT NULL REFERENCES players(tag) ON DELETE CASCADE,
    attacked_at TIMESTAMPTZ NOT NULL,
    opponent_tag TEXT        NOT NULL DEFAULT '',
    UNIQUE (player_tag, attacked_at, opponent_tag)
);

CREATE INDEX IF NOT EXISTS idx_player_attack_events_player_time
    ON player_attack_events (player_tag, attacked_at DESC);
