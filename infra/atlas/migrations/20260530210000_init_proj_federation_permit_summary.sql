-- Federation BC: Permit summary read model.
--
-- Folds the Permit aggregate's lifecycle events into the
-- `proj_federation_permit_summary` read model used by the list / get
-- slices that ship in Stage 2b/2c.
--
-- Subscribed events (apply order):
--   - PermitDefined    -> INSERT (status='Defined', defined_at=occurred_at)
--   - PermitActivated  -> UPDATE status='Active',    activated_at=occurred_at
--   - PermitSuspended  -> UPDATE status='Suspended', suspended_at=occurred_at
--   - PermitResumed    -> UPDATE status='Active',    resumed_at=occurred_at
--   - PermitRevoked    -> UPDATE status='Revoked',   revoked_at=occurred_at
--
-- ## Polymorphic terms (tagged union)
--
-- Permit carries `terms: OutboundTerms | InboundTerms`. The discriminator
-- column `terms_kind` is one of {'Outbound', 'Inbound'} (matching the
-- aggregate's Direction StrEnum verbatim) and the per-direction columns
-- are nullable; an exclusive-arc CHECK constraint enforces that exactly
-- one arc is populated.
--
-- ## Path C lifecycle timestamps
--
-- Genesis timestamp `defined_at` is NOT NULL; transition timestamps
-- (activated_at, suspended_at, resumed_at, revoked_at) start NULL and
-- are filled by the projection from the event envelope `occurred_at`.

CREATE TABLE proj_federation_permit_summary (
    permit_id                              UUID        PRIMARY KEY,
    peer_facility_id                       TEXT        NOT NULL,
    direction                              TEXT        NOT NULL CHECK (
        direction IN ('Outbound', 'Inbound')
    ),
    allowed_credentials                    JSONB       NOT NULL,
    allowed_payload_types                  JSONB       NOT NULL,
    allowed_artifact_kinds                 JSONB       NOT NULL,
    abi_tier_floor                         TEXT        NOT NULL,
    expires_at                             TIMESTAMPTZ,
    defined_by_actor_id                    UUID        NOT NULL,
    status                                 TEXT        NOT NULL CHECK (
        status IN ('Defined', 'Active', 'Suspended', 'Revoked')
    ),

    terms_kind                             TEXT        NOT NULL CHECK (
        terms_kind IN ('Outbound', 'Inbound')
    ),

    read_scope                             JSONB,
    onward_action_scope                    JSONB,
    scope_set                              JSONB,

    accepted_canonicalization_versions     JSONB,
    required_receipt_kinds                 JSONB,
    publisher_grant_correlation_handle     TEXT,
    inbound_allowed_artifact_kinds         JSONB,

    defined_at                             TIMESTAMPTZ NOT NULL,
    activated_at                           TIMESTAMPTZ,
    suspended_at                           TIMESTAMPTZ,
    resumed_at                             TIMESTAMPTZ,
    revoked_at                             TIMESTAMPTZ,
    updated_at                             TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT proj_federation_permit_summary_terms_exclusive_arc CHECK (
        (terms_kind = 'Outbound'
         AND read_scope IS NOT NULL
         AND onward_action_scope IS NOT NULL
         AND scope_set IS NOT NULL
         AND accepted_canonicalization_versions IS NULL
         AND required_receipt_kinds IS NULL
         AND publisher_grant_correlation_handle IS NULL
         AND inbound_allowed_artifact_kinds IS NULL)
        OR
        (terms_kind = 'Inbound'
         AND accepted_canonicalization_versions IS NOT NULL
         AND required_receipt_kinds IS NOT NULL
         AND inbound_allowed_artifact_kinds IS NOT NULL
         AND read_scope IS NULL
         AND onward_action_scope IS NULL
         AND scope_set IS NULL)
    ),

    CONSTRAINT proj_federation_permit_summary_terms_kind_matches_direction CHECK (
        terms_kind = direction
    )
);

-- Hot-path filter: all permits for a given peer facility, grouped by
-- status (the common operator query).
CREATE INDEX proj_federation_permit_summary_peer_status_idx
    ON proj_federation_permit_summary (peer_facility_id, status);

-- Hot-path filter: all permits in a given direction, grouped by status
-- (the federation dashboard view).
CREATE INDEX proj_federation_permit_summary_direction_status_idx
    ON proj_federation_permit_summary (direction, status);

-- Background scan: find permits about to expire. expires_at-nullable
-- rows are excluded via partial index.
CREATE INDEX proj_federation_permit_summary_expiry_idx
    ON proj_federation_permit_summary (status, expires_at)
    WHERE expires_at IS NOT NULL;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_federation_permit_summary TO cora_app;

-- Row-Level Security: defense-in-depth on permit terms.
ALTER TABLE proj_federation_permit_summary ENABLE ROW LEVEL SECURITY;
ALTER TABLE proj_federation_permit_summary FORCE  ROW LEVEL SECURITY;

CREATE POLICY proj_federation_permit_summary_cora_app_read
    ON proj_federation_permit_summary FOR SELECT
    TO cora_app
    USING (true);

CREATE POLICY proj_federation_permit_summary_cora_app_write
    ON proj_federation_permit_summary FOR ALL
    TO cora_app
    USING (true)
    WITH CHECK (true);

INSERT INTO projection_bookmarks (name)
VALUES ('proj_federation_permit_summary')
ON CONFLICT DO NOTHING;
