-- Phase γ PII vault: actor_profile table holds human-facing Actor PII
-- (name today; email/phone/ORCID/affiliation later as nullable columns
-- via additive ALTER TABLE).
--
-- Single mutable table, one row per Actor regardless of kind (HUMAN /
-- AGENT / SERVICE_ACCOUNT — uniform shape; HUMAN rows carry human PII,
-- AGENT/SERVICE_ACCOUNT rows carry display labels). Erasure = scrub
-- then DELETE the row, plus emit ActorProfileForgotten event in the
-- same transaction.
--
-- Naming: BC-prefixed via aggregate name (matches the existing
-- entries_decision_reasonings / proj_access_actor_summary convention).
--
-- Schema decisions:
--   - actor_id is both PK and (application-level) link to the Actor
--     aggregate's stream_id. No SQL FK to events.stream_id because the
--     events table is INSERT-only at the role level per
--     project_immutability_guarantee; FK enforcement is application-
--     discipline (both writes happen in the same transaction).
--   - name is NOT NULL with a CHECK constraint mirroring the
--     ActorName VO (1-200 chars after trim, enforced at write time
--     by the VO; the CHECK is defense-in-depth).
--   - created_at is application-supplied (matches the event's
--     occurred_at). updated_at defaults to now() at row creation;
--     explicitly SET on rename writes (deferred slice).
--   - No forgotten_at column. Soft-delete column itself would be PII
--     ("actor X existed and asked to be forgotten on Y"). Audit lives
--     in the ActorProfileForgotten event envelope (principal_id +
--     occurred_at). Future "list of forgotten actors" view builds
--     from those events via a deferred projection.
--   - No UNIQUE constraint on name: realistic for two operators to
--     share a display name; UNIQUE under RLS leaks via constraint-
--     violation timing.
--   - No LOWER(name) index. Add when the first case-insensitive
--     lookup slice ships (per project_deferred Phase γ entry).
--
-- RLS posture (defense-in-depth on the one mutable PII surface):
--   - ENABLE ROW LEVEL SECURITY: turn on policy enforcement. Without
--     a policy this is default-deny — the two CREATE POLICY statements
--     grant the access cora_app needs.
--   - FORCE ROW LEVEL SECURITY: defense-in-depth against accidental
--     owner-role (cora) queries at runtime. Without FORCE, table-owner
--     queries bypass policy silently — exactly the failure mode the
--     cora_app role split was designed to prevent for events.
--   - Two flat permissive policies for cora_app (read + write). Both
--     USING (true) for v1: cora_app is the only runtime role.
--     Per-actor RESTRICTIVE policies layer on top when actor
--     self-service ships (project_deferred Phase γ entry).
--
-- Audit logging is deliberately NOT enabled at the DB level (no
-- pgaudit, no audit triggers). The events.principal_id + the
-- ActorProfileForgotten event are the canonical write-audit record;
-- app-layer structured logs cover read access. pgaudit adoption is
-- trigger-gated (project_deferred Phase γ entry).

CREATE TABLE actor_profile (
    actor_id    UUID        PRIMARY KEY,
    name        TEXT        NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE actor_profile IS
    'PII vault for Actor (memory/project_pii_vault). Mutable. Erasure = scrub-then-DELETE row + emit ActorProfileForgotten in same txn.';
COMMENT ON COLUMN actor_profile.actor_id IS
    'Matches Actor aggregate stream_id. No SQL FK to events (INSERT-only role); transactional discipline at write time.';
COMMENT ON COLUMN actor_profile.name IS
    'Display name. 1-200 chars. Future PII fields (email, phone, ORCID, affiliation) land as nullable columns via additive ALTER TABLE.';

-- Mutable PII vault: cora_app gets full CRUD. DELETE is the erasure
-- mechanism; UPDATE is both the rename path and the scrub-before-DELETE
-- step in forget_actor.
GRANT SELECT, INSERT, UPDATE, DELETE ON actor_profile TO cora_app;

-- Row-Level Security: defense-in-depth.
ALTER TABLE actor_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE actor_profile FORCE  ROW LEVEL SECURITY;

CREATE POLICY actor_profile_cora_app_read
    ON actor_profile FOR SELECT
    TO cora_app
    USING (true);

CREATE POLICY actor_profile_cora_app_write
    ON actor_profile FOR ALL
    TO cora_app
    USING (true)
    WITH CHECK (true);
