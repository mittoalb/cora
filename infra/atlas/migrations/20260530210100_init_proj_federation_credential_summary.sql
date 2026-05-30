-- Federation BC: Credential summary read model.
--
-- Folds the Credential aggregate's lifecycle events into the
-- `proj_federation_credential_summary` read model used by the list / get
-- slices that ship in Stage 2b/2c.
--
-- Credential carries secret-material refs (UUID-style opaque handles
-- into the SecretStore port). The refs themselves are non-PII pointers,
-- but they are sensitive material in the sense that a leaked
-- `secret_ref` plus an unscoped SecretStore.load would surface the
-- backing material. RLS-FORCE matches the actor_profile precedent
-- (per memory/project_pii_vault_implementation_design): ENABLE +
-- FORCE row level security, two flat policies for cora_app, defense
-- in depth against accidental owner-role bypass.
--
-- Subscribed events (apply order):
--   - CredentialRegistered          -> INSERT (status='Active',
--                                              registered_at=occurred_at)
--   - CredentialRotationStarted     -> UPDATE rotation_pending_*,
--                                             rotation_started_at
--   - CredentialRotationCompleted   -> UPDATE secret_ref +
--                                             public_material_ref to the
--                                             pending values; clear
--                                             rotation_pending_*; bump
--                                             expires_at; status='Active'
--   - CredentialRotationAborted     -> UPDATE clear rotation_pending_*;
--                                             clear rotation_started_at
--   - CredentialRevoked             -> UPDATE status='Revoked',
--                                             revoked_at=occurred_at
--
-- Identity tuple: (facility_id, audience, purpose) is unique per the
-- aggregate's design lock. Re-registration after revocation requires
-- the operator to first delete the prior row (a deferred slice; until
-- then the UNIQUE blocks accidental double-register).

CREATE TABLE proj_federation_credential_summary (
    credential_id                          UUID        PRIMARY KEY,
    facility_id                            TEXT        NOT NULL,
    audience                               TEXT        NOT NULL,
    purpose                                TEXT        NOT NULL CHECK (
        purpose IN (
            'Signing', 'Verification', 'Authentication', 'Encryption',
            'SealOnlineSigning', 'SealOfflineRoot'
        )
    ),
    secret_ref                             TEXT        NOT NULL CHECK (
        length(secret_ref) > 0
    ),
    public_material_ref                    TEXT,
    expires_at                             TIMESTAMPTZ,
    status                                 TEXT        NOT NULL CHECK (
        status IN ('Active', 'Rotating', 'Revoked')
    ),
    rotation_pending_secret_ref            TEXT,
    rotation_pending_public_material_ref   TEXT,

    registered_at                          TIMESTAMPTZ NOT NULL,
    rotation_started_at                    TIMESTAMPTZ,
    revoked_at                             TIMESTAMPTZ,
    updated_at                             TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT proj_federation_credential_summary_identity_unique
        UNIQUE (facility_id, audience, purpose)
);

COMMENT ON TABLE proj_federation_credential_summary IS
    'Federation credential summary read model. Holds opaque refs into the SecretStore port; never the secret material itself. RLS-FORCE per actor_profile precedent (memory/project_pii_vault_implementation_design).';
COMMENT ON COLUMN proj_federation_credential_summary.secret_ref IS
    'Opaque handle into SecretStore. Length > 0 enforced at DB level (defense in depth).';

-- Hot-path filter: all credentials for a facility / audience pair.
CREATE INDEX proj_federation_credential_summary_facility_audience_idx
    ON proj_federation_credential_summary (facility_id, audience);

-- Background scan: find credentials about to expire.
CREATE INDEX proj_federation_credential_summary_expiry_idx
    ON proj_federation_credential_summary (status, expires_at)
    WHERE expires_at IS NOT NULL;

-- Mutable read model. cora_app gets full CRUD (DELETE supports the
-- post-revocation cleanup that re-registration requires).
GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_federation_credential_summary TO cora_app;

-- Row-Level Security: defense-in-depth on credential refs.
ALTER TABLE proj_federation_credential_summary ENABLE ROW LEVEL SECURITY;
ALTER TABLE proj_federation_credential_summary FORCE  ROW LEVEL SECURITY;

CREATE POLICY proj_federation_credential_summary_cora_app_read
    ON proj_federation_credential_summary FOR SELECT
    TO cora_app
    USING (true);

CREATE POLICY proj_federation_credential_summary_cora_app_write
    ON proj_federation_credential_summary FOR ALL
    TO cora_app
    USING (true)
    WITH CHECK (true);

INSERT INTO projection_bookmarks (name)
VALUES ('proj_federation_credential_summary')
ON CONFLICT DO NOTHING;
