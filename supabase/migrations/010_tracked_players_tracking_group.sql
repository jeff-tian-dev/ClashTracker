-- Split manually pinned players: clan (July) vs external. Existing rows default to clan_july.

ALTER TABLE tracked_players
    ADD COLUMN IF NOT EXISTS tracking_group TEXT NOT NULL DEFAULT 'clan_july';

ALTER TABLE tracked_players
    DROP CONSTRAINT IF EXISTS tracked_players_tracking_group_check;

ALTER TABLE tracked_players
    ADD CONSTRAINT tracked_players_tracking_group_check
    CHECK (tracking_group IN ('clan_july', 'external'));
