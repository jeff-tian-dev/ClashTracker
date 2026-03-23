-- 005_legends.sql
-- Table: legends_battles (Legends League daily battle tracking)

CREATE TABLE IF NOT EXISTS legends_battles (
    id              BIGSERIAL PRIMARY KEY,
    player_tag      TEXT NOT NULL REFERENCES players(tag) ON DELETE CASCADE,
    opponent_tag    TEXT NOT NULL,
    opponent_name   TEXT,
    is_attack       BOOLEAN NOT NULL,
    stars           INT NOT NULL,
    destruction_pct INT NOT NULL,
    trophies        INT NOT NULL,
    legends_day     DATE NOT NULL,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (player_tag, opponent_tag, is_attack, stars, destruction_pct, legends_day)
);

CREATE INDEX IF NOT EXISTS idx_legends_battles_player_day ON legends_battles(player_tag, legends_day);
CREATE INDEX IF NOT EXISTS idx_legends_battles_day ON legends_battles(legends_day);
