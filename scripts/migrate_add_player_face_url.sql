-- Run against citybet_virtuals when upgrading an existing database:
-- psql -U postgres -d citybet_virtuals -f scripts/migrate_add_player_face_url.sql

ALTER TABLE public.players
    ADD COLUMN IF NOT EXISTS player_face_url VARCHAR(500);
