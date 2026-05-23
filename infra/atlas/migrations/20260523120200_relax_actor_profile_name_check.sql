-- Phase γ forget_actor: allow zero-length `actor_profile.name` so the
-- scrub-before-delete UPDATE (`SET name = ''`) does not trip the
-- original `length(name) BETWEEN 1 AND 200` CHECK from
-- 20260523120000_init_actor_profile.sql.
--
-- The application-layer `ActorName` value object still enforces 1-200
-- chars at WRITE time (register_actor / define_agent paths); the DB
-- constraint stays as defense-in-depth on the upper bound. The lower
-- bound is intentionally relaxed so the scrub UPDATE can overwrite a
-- live row with the empty-string marker before DELETE clears it,
-- per the Postgres-canonical WAL/dead-tuple PII cleanup pattern.
--
-- Forward-only per [[project_forward_only_migrations]]. Idempotent
-- via DROP IF EXISTS / re-ADD.

ALTER TABLE actor_profile
    DROP CONSTRAINT IF EXISTS actor_profile_name_check;

ALTER TABLE actor_profile
    ADD CONSTRAINT actor_profile_name_check
        CHECK (length(name) <= 200);
