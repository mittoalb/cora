-- Seed default Surfaces + V2 Bootstrap Policy (Phase B Iter C).
-- Atomic via BEGIN/COMMIT per design lock AH14: partial-fail would
-- leave V2 policy referencing non-existent Surfaces — evaluate would
-- Allow on phantom, traversal audit silently skips. See
-- memory/project_conduit_injection_design.md.
--
-- Seeds:
--   - SYSTEM_HTTP_SURFACE_ID                = ...0020 (kind=http)
--   - SYSTEM_MCP_STDIO_SURFACE_ID           = ...0021 (kind=mcp_stdio)
--   - SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID = ...0022 (kind=mcp_streamable_http)
--   - SYSTEM_BOOTSTRAP_POLICY_V2_ID         = ...0002 (bound to HTTP surface)
--
-- Constants live in cora.trust._bootstrap. Forward-only-migrations
-- discipline: V1 policy stream (...0001) stays in the event log
-- forever — operators flip TRUST_POLICY_ID env var to ...0002.

BEGIN;

-- HTTP surface
INSERT INTO events (
    event_id, stream_type, stream_id, version, event_type,
    payload, metadata, correlation_id, principal_id, occurred_at
) VALUES (
    gen_random_uuid(), 'Surface',
    '00000000-0000-0000-0000-000000000020'::uuid, 1, 'SurfaceDefined',
    jsonb_build_object(
        'surface_id',  '00000000-0000-0000-0000-000000000020',
        'name',        'System HTTP',
        'kind',        'http',
        'occurred_at', '2026-05-19T00:00:00+00:00'
    ),
    jsonb_build_object('command', 'SystemBootstrap'),
    '00000000-0000-0000-0000-000000000000'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    '2026-05-19 00:00:00+00'::timestamptz
)
ON CONFLICT (stream_type, stream_id, version) DO NOTHING;

-- MCP stdio surface
INSERT INTO events (
    event_id, stream_type, stream_id, version, event_type,
    payload, metadata, correlation_id, principal_id, occurred_at
) VALUES (
    gen_random_uuid(), 'Surface',
    '00000000-0000-0000-0000-000000000021'::uuid, 1, 'SurfaceDefined',
    jsonb_build_object(
        'surface_id',  '00000000-0000-0000-0000-000000000021',
        'name',        'System MCP stdio',
        'kind',        'mcp_stdio',
        'occurred_at', '2026-05-19T00:00:00+00:00'
    ),
    jsonb_build_object('command', 'SystemBootstrap'),
    '00000000-0000-0000-0000-000000000000'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    '2026-05-19 00:00:00+00'::timestamptz
)
ON CONFLICT (stream_type, stream_id, version) DO NOTHING;

-- MCP streamable-http surface
INSERT INTO events (
    event_id, stream_type, stream_id, version, event_type,
    payload, metadata, correlation_id, principal_id, occurred_at
) VALUES (
    gen_random_uuid(), 'Surface',
    '00000000-0000-0000-0000-000000000022'::uuid, 1, 'SurfaceDefined',
    jsonb_build_object(
        'surface_id',  '00000000-0000-0000-0000-000000000022',
        'name',        'System MCP streamable-http',
        'kind',        'mcp_streamable_http',
        'occurred_at', '2026-05-19T00:00:00+00:00'
    ),
    jsonb_build_object('command', 'SystemBootstrap'),
    '00000000-0000-0000-0000-000000000000'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    '2026-05-19 00:00:00+00'::timestamptz
)
ON CONFLICT (stream_type, stream_id, version) DO NOTHING;

-- V2 Bootstrap Policy — bound to HTTP surface, otherwise identical
-- scope to V1 ({DefinePolicy, RegisterActor} for SYSTEM_PRINCIPAL_ID).
INSERT INTO events (
    event_id, stream_type, stream_id, version, event_type,
    payload, metadata, correlation_id, principal_id, occurred_at
) VALUES (
    gen_random_uuid(), 'Policy',
    '00000000-0000-0000-0000-000000000002'::uuid, 1, 'PolicyDefined',
    jsonb_build_object(
        'policy_id',            '00000000-0000-0000-0000-000000000002',
        'name',                 'System Bootstrap Policy V2',
        'conduit_id',           '00000000-0000-0000-0000-000000000000',
        'surface_id',           '00000000-0000-0000-0000-000000000020',
        'permitted_principals', jsonb_build_array('00000000-0000-0000-0000-000000000000'),
        'permitted_commands',   jsonb_build_array('DefinePolicy', 'RegisterActor'),
        'occurred_at',          '2026-05-19T00:00:00+00:00'
    ),
    jsonb_build_object('command', 'SystemBootstrap'),
    '00000000-0000-0000-0000-000000000000'::uuid,
    '00000000-0000-0000-0000-000000000000'::uuid,
    '2026-05-19 00:00:00+00'::timestamptz
)
ON CONFLICT (stream_type, stream_id, version) DO NOTHING;

COMMIT;
