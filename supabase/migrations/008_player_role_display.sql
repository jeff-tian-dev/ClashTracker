-- Normalize players.role to dashboard labels (matches ingestion normalize_player_role).

UPDATE players SET role = 'Member' WHERE role = 'member';
UPDATE players SET role = 'Elder' WHERE role IN ('admin', 'elder');
UPDATE players SET role = 'Co-leader' WHERE role = 'coLeader';
UPDATE players SET role = 'Leader' WHERE role = 'leader';
