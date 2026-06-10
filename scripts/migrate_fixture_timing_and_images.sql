-- Run against citybet_virtuals when upgrading an existing database:
-- psql -U postgres -d citybet_virtuals -f scripts/migrate_fixture_timing_and_images.sql

ALTER TABLE public.fixtures
    ADD COLUMN IF NOT EXISTS show_at_ms BIGINT NOT NULL DEFAULT 0;

ALTER TABLE public.fixtures
    ADD COLUMN IF NOT EXISTS fixture_image_url VARCHAR(500);
