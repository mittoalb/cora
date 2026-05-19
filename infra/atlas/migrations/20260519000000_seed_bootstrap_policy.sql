-- Seed the System Bootstrap Policy.
--
-- FIRST migration to insert event-sourced data into the `events`
-- table (every prior migration is schema-only). Design rationale +
-- anti-hooks: `memory/project_bootstrap_policy_design.md` (Phase A,
-- Stage 1 lock 2026-05-18).
--
-- The bootstrap policy closes the chicken-and-egg in
-- `cora/trust/authorize.py`: without a policy that permits
-- `DefinePolicy`, you cannot define policies through the API.
-- The 3-step dance (start permissive → POST policy → restart)
-- collapses to a 1-step env-var set:
--
--     TRUST_POLICY_ID=00000000-0000-0000-0000-000000000001
--
-- The policy UUID is a fixed code constant
-- (`cora.trust._bootstrap.SYSTEM_BOOTSTRAP_POLICY_ID`), not a
-- Settings value — K8s `cluster-admin` precedent (anti-hook AH1:
-- configurable bootstrap defeats the bootstrap).
--
-- ## Payload shape
--
-- The JSON payload must match `to_payload` in
-- `cora/trust/aggregates/policy/events.py` byte-for-byte:
--   - `permitted_principals`: sorted by UUID string form
--   - `permitted_commands`: sorted alphabetically
-- Any drift would still fold correctly via `from_stored` but would
-- surprise byte-comparison tooling (anti-hook AH7).
--
-- ## Idempotency
--
-- `ON CONFLICT (stream_type, stream_id, version) DO NOTHING` makes
-- re-runs silent no-ops. The unique constraint comes from
-- `events_stream_version_unique` in the init migration. Forward-only
-- per `memory/project_forward_only_migrations.md`: any future change
-- to this seed lands as a NEW compensating migration, never as an
-- UPDATE here.
--
-- ## Scope (minimum needed)
--
-- The seed permits SYSTEM_PRINCIPAL_ID (nil UUID) to execute only
-- `DefinePolicy` + `RegisterActor` on the nil conduit. That is the
-- minimum to register a real admin Actor and promote a real admin
-- Policy. Anti-hook AH3 (scope creep) forbids widening this set;
-- operators promote a real admin Policy instead.

INSERT INTO events (
    event_id,
    stream_type,
    stream_id,
    version,
    event_type,
    payload,
    metadata,
    correlation_id,
    principal_id,
    occurred_at
) VALUES (
    gen_random_uuid(),
    'Policy',
    '00000000-0000-0000-0000-000000000001'::uuid,
    1,
    'PolicyDefined',
    jsonb_build_object(
        'policy_id',            '00000000-0000-0000-0000-000000000001',
        'name',                 'System Bootstrap Policy',
        'conduit_id',           '00000000-0000-0000-0000-000000000000',
        'permitted_principals', jsonb_build_array('00000000-0000-0000-0000-000000000000'),
        'permitted_commands',   jsonb_build_array('DefinePolicy', 'RegisterActor'),
        'occurred_at',          '2026-05-18T00:00:00+00:00'
    ),
    jsonb_build_object('command', 'SystemBootstrap'),
    '00000000-0000-0000-0000-000000000000'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    '2026-05-18 00:00:00+00'::timestamptz
)
ON CONFLICT (stream_type, stream_id, version) DO NOTHING;
