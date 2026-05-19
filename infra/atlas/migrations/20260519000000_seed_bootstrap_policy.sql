-- Seed the System Bootstrap Policy (first event-seeding migration).
-- Payload sorted to match `to_payload` byte-for-byte; ON CONFLICT
-- makes re-runs no-ops. See memory/project_bootstrap_policy_design.md.

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
