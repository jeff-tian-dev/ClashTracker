-- Deferred second pass for Legends battle log ingestion (see apps/ingestion/legends.py).

CREATE TABLE IF NOT EXISTS legends_confirmation_queue (
    id              BIGSERIAL PRIMARY KEY,
    player_tag      TEXT        NOT NULL REFERENCES players(tag) ON DELETE CASCADE,
    cursor_snapshot JSONB       NOT NULL,
    run_after       TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_legends_confirmation_queue_run_after
    ON legends_confirmation_queue (run_after);
