-- Phase 8d foundation hardening: app-role separation for event-store
-- immutability.
--
-- Implements the locked decision in
-- `memory/project_immutability_guarantee.md`: the events table (and
-- every entries_* table) is INSERT-only at the database role level,
-- not just by application convention. Migrations run as the database
-- owner (cora); the app pool connects as `cora_app` which has
-- SELECT + INSERT only on append-only tables. Any UPDATE / DELETE
-- attempt against `events` or `entries_*` from the app role fails
-- at the database with an authorization error, turning immutability
-- from a code-review convention into a database-enforced guarantee.
--
-- Production deployments opt in by setting `DATABASE_URL` to use the
-- `cora_app` credentials. Local dev and tests still use the owner
-- role (`cora`) for fixtures and migrations; one integration test
-- explicitly opens a `cora_app`-credentialed pool to prove the
-- REVOKE actually denies UPDATE / DELETE.
--
-- Why CREATE ROLE in a migration:
--   The role is a cluster-level object (not per-database), so this
--   `CREATE ROLE` runs once and is idempotent. The grants and
--   revokes are per-database; they apply to each database the
--   migration runs against (including the testcontainers session
--   database that becomes the per-test template via
--   `CREATE DATABASE ... TEMPLATE ...`).
--
-- Why password is `cora_app`:
--   Local-dev convention. Production deployments override via the
--   secret store; the password set here is irrelevant once an
--   external credential rotates it. Greenfield: no production
--   deployments exist yet.
--
-- The REVOKE statements at the bottom are belt-and-suspenders
-- against future migrations that might GRANT ALL on append-only
-- tables. The grants above already do not include UPDATE / DELETE,
-- so the REVOKE is documentation and protection, not the only
-- enforcement layer.

DO $do$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'cora_app') THEN
        CREATE ROLE cora_app WITH LOGIN PASSWORD 'cora_app';
    END IF;
END
$do$;

GRANT USAGE ON SCHEMA public TO cora_app;

-- Append-only tables: SELECT + INSERT only. UPDATE / DELETE / TRUNCATE
-- never granted; explicit REVOKE below makes that intent
-- machine-checkable.
GRANT SELECT, INSERT ON events                        TO cora_app;
GRANT SELECT, INSERT ON entries_conduit_traversals    TO cora_app;
GRANT SELECT, INSERT ON entries_decision_reasonings   TO cora_app;

-- Mutable cache: idempotency keys are TTL-pruned and updated under
-- the two-phase claim pattern (Phase-2 idempotency hardening).
GRANT SELECT, INSERT, UPDATE, DELETE ON idempotency_keys TO cora_app;

-- bigserial sequences need USAGE for nextval().
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO cora_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO cora_app;

-- Belt-and-suspenders: REVOKE UPDATE / DELETE / TRUNCATE on every
-- append-only table from cora_app. Redundant with the omission
-- above, but protects against:
--   1. Future migrations that GRANT ALL ON ... TO cora_app by
--      mistake (the REVOKE here would still apply because REVOKE
--      acts on subsequent privilege changes only when re-issued;
--      the architecture-fitness test enforces that every new
--      append-only table carries its own REVOKE statement).
--   2. Misreading of intent: a present REVOKE is documented
--      enforcement, not just absence-of-grant.
REVOKE UPDATE, DELETE, TRUNCATE ON events                      FROM cora_app;
REVOKE UPDATE, DELETE, TRUNCATE ON entries_conduit_traversals  FROM cora_app;
REVOKE UPDATE, DELETE, TRUNCATE ON entries_decision_reasonings FROM cora_app;
