-- April push / Legends: upper (1) vs lower (2) bracket for July tracked pins.

ALTER TABLE tracked_players
    ADD COLUMN IF NOT EXISTS legends_bracket SMALLINT NOT NULL DEFAULT 1;

ALTER TABLE tracked_players
    DROP CONSTRAINT IF EXISTS tracked_players_legends_bracket_check;

ALTER TABLE tracked_players
    ADD CONSTRAINT tracked_players_legends_bracket_check
    CHECK (legends_bracket IN (1, 2));
