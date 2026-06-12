-- CoC Legend League tiers share the name "Legend League"; distinguish by leagueTier.id.
ALTER TABLE players
    ADD COLUMN IF NOT EXISTS league_tier_id INTEGER;

CREATE INDEX IF NOT EXISTS idx_players_league_tier_id
    ON players (league_tier_id)
    WHERE league_tier_id IS NOT NULL;
