-- Phase γ PII vault: backfill actor_profile from the existing
-- proj_access_actor_summary projection.
--
-- Source: proj_access_actor_summary (already extracted + length-
-- validated names from V1 ActorRegistered events; safer than parsing
-- event payloads directly, which would require duplicating the from_stored
-- dispatch in SQL).
--
-- Ordering: this migration runs AFTER 20260523120000_init_actor_profile.sql
-- and BEFORE the new Python code is live (Atlas runs all pending
-- migrations to completion before app startup). Post-deploy reads find
-- the table populated.
--
-- Idempotent: ON CONFLICT DO NOTHING ensures the migration can re-run
-- safely on an already-backfilled DB. cora_app re-deploys won't
-- duplicate-fail.

INSERT INTO actor_profile (actor_id, name, created_at)
SELECT actor_id, name, created_at
FROM proj_access_actor_summary
ON CONFLICT (actor_id) DO NOTHING;
