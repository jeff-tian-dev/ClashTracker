-- Use display_name instead of name (avoids ambiguous JSON/key handling with generic "name").
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'tracked_players'
          AND column_name = 'name'
    ) THEN
        ALTER TABLE tracked_players RENAME COLUMN name TO display_name;
    ELSIF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'tracked_players'
          AND column_name = 'display_name'
    ) THEN
        ALTER TABLE tracked_players
            ADD COLUMN display_name TEXT NOT NULL DEFAULT '';
    END IF;
END $$;
