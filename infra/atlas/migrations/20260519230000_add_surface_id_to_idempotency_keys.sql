-- Phase B Iter C-2c: extend idempotency-key namespace with surface_id.
--
-- Per the IETF Idempotency-Key draft (§5 Security Considerations,
-- draft-ietf-httpapi-idempotency-key-header-07): "implement a unique
-- composite key as the idempotent cache lookup key. For example, a
-- composite key MAY be implemented by combining the idempotency key
-- with other server-side context attributes."
--
-- Before this migration, the cache lookup key was (principal_id, key).
-- The Phase B Iter C-2b surface_id sweep means every command now
-- arrives via a specific Surface (HTTP / MCP / future stdio). Under V2
-- per-surface authorization policies (forthcoming), a retry of the
-- same (principal_id, key, body) from a DIFFERENT Surface must NOT
-- return the cached Allow result from the original Surface — the new
-- Surface's policy may deny. Server-side composite key with surface_id
-- as the third namespace component resolves this: independent cache
-- slot per (principal_id, key, surface_id) triple, each gated by its
-- own Surface's policy.
--
-- This is server-side composition (AH1: surface_id is process-pinned,
-- never client-asserted), so it's not visible in the IETF "different
-- payload = 422" rule — that still applies via command_hash. This
-- migration adds a SECOND dimension to the cache namespace, parallel
-- to principal_id (which already prevents cross-tenant cache hits).
--
-- ## Schema change
--
--   - ADD COLUMN surface_id uuid NOT NULL DEFAULT nil-sentinel.
--     Existing rows (pre-Iter-C deploys, no V2 policies) all get the
--     nil sentinel, matching their original "no surface dimension"
--     semantic. No behavioral break for V1 deployments.
--   - DROP old PRIMARY KEY (principal_id, key).
--   - ADD new PRIMARY KEY (principal_id, key, surface_id). Constant
--     fill on existing rows keeps uniqueness (the old PK guaranteed
--     uniqueness of (principal_id, key); adding a constant third
--     column preserves it).
--
-- The PK swap re-creates the unique B-tree index PG uses for the hot
-- claim path. asyncpg's per-connection prepared-statement cache will
-- re-plan on first use after deploy; cost is one extra plan per
-- worker on cold start.
--
-- ## Forward-only
--
-- Per project_forward_only_migrations memory: forward-only. No DOWN
-- script. Rollback = NEW migration that drops surface_id + restores
-- the old PK.
--
-- ## Atlas safety
--
-- ADD COLUMN (with NOT NULL + DEFAULT) is allowed; PG fills existing
-- rows synchronously from the DEFAULT (table-rewriting in PG <11,
-- in-place metadata-only in PG 11+). DROP CONSTRAINT + ADD PRIMARY
-- KEY are not on the forbidden list. No safety opt-out comment needed.

ALTER TABLE idempotency_keys
    ADD COLUMN surface_id uuid NOT NULL
        DEFAULT '00000000-0000-0000-0000-000000000000'::uuid;

ALTER TABLE idempotency_keys
    DROP CONSTRAINT idempotency_keys_pkey;

ALTER TABLE idempotency_keys
    ADD PRIMARY KEY (principal_id, key, surface_id);
