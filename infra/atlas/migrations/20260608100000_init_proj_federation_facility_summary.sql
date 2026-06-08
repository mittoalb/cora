-- Federation BC: Facility summary read model.
--
-- Folds the Facility aggregate's lifecycle events into the
-- `proj_federation_facility_summary` read model used by future list /
-- get slices. Per Session 5 Slice 5 Sub-Slice B of the structural-scope
-- masquerade resolution, this lands the Facility tier as an additive
-- aggregate; no cross-BC binding yet (Asset.facility_id / Supply.facility_id
-- ship in slices 7-8).
--
-- Subscribed events (apply order):
--   - FacilityRegistered          -> INSERT (status='Active',
--                                            registered_at=occurred_at)
--   - FacilityDecommissioned      -> UPDATE status='Decommissioned',
--                                           decommissioned_at,
--                                           decommissioned_by
--
-- Identity tuples per the two-tier identity contract:
--   - facility_id (UUID): internal-opaque PK; spine references within
--     ONE deployment use this.
--   - code (TEXT): cross-deployment convergent slug; cross-BC and
--     cross-deployment references MUST use this. UNIQUE across the
--     whole table (no partial WHERE clause) per the L2 lock; codes are
--     immutable post-creation and may not be reused for a new Active
--     facility after decommissioning.
--
-- Structural invariants enforced at the DB tier:
--   - kind is closed to ('Site', 'Area'); Institution and Sector are
--     deferred per the design memo.
--   - status is closed to ('Active', 'Decommissioned').
--   - Site has no parent: kind='Site' implies parent_id IS NULL.
--   - Area has parent: kind='Area' implies parent_id IS NOT NULL.

CREATE TABLE proj_federation_facility_summary (
    facility_id                  UUID         PRIMARY KEY,
    code                         TEXT         NOT NULL,
    display_name                 TEXT         NOT NULL CHECK (
        length(display_name) > 0
    ),
    kind                         TEXT         NOT NULL CHECK (
        kind IN ('Site', 'Area')
    ),
    parent_id                    UUID,
    status                       TEXT         NOT NULL CHECK (
        status IN ('Active', 'Decommissioned')
    ),
    alternate_identifiers        JSONB        NOT NULL DEFAULT '[]'::jsonb,
    trust_anchor_credential_ids  JSONB        NOT NULL DEFAULT '[]'::jsonb,
    persistent_id                JSONB,

    registered_at                TIMESTAMPTZ  NOT NULL,
    registered_by                UUID         NOT NULL,
    decommissioned_at            TIMESTAMPTZ,
    decommissioned_by            UUID,
    updated_at                   TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT proj_federation_facility_summary_code_unique
        UNIQUE (code),
    CONSTRAINT proj_federation_facility_summary_site_no_parent CHECK (
        kind <> 'Site' OR parent_id IS NULL
    ),
    CONSTRAINT proj_federation_facility_summary_area_has_parent CHECK (
        kind <> 'Area' OR parent_id IS NOT NULL
    )
);

COMMENT ON TABLE proj_federation_facility_summary IS
    'Federation Facility summary read model. Two-tier identity (facility_id UUID PK + code cross-deployment slug); kind {Site, Area} day-one; status {Active, Decommissioned} terminal FSM.';
COMMENT ON COLUMN proj_federation_facility_summary.code IS
    'Cross-deployment convergent facility slug. UNIQUE across the table; immutable post-creation; codes of decommissioned facilities stay reserved.';
COMMENT ON COLUMN proj_federation_facility_summary.parent_id IS
    'Parent Facility id. NULL for kind=Site; non-NULL for kind=Area. Cross-stream parent-existence and parent-kind=Site checks are projection-side concerns deferred to slice 6.';
COMMENT ON COLUMN proj_federation_facility_summary.trust_anchor_credential_ids IS
    'Structural fold of the SealCrossFacilityBindingError defense-in-depth string-equality check. Empty default; populated only for kind=Site rows by future slice 6 add/remove binding slices.';

-- Hot-path filter: list active facilities by kind for operator-facing
-- list endpoints (future slice).
CREATE INDEX proj_federation_facility_summary_kind_status_idx
    ON proj_federation_facility_summary (kind, status);

-- Tree-walk filter: list children of a given parent (future slice).
CREATE INDEX proj_federation_facility_summary_parent_idx
    ON proj_federation_facility_summary (parent_id)
    WHERE parent_id IS NOT NULL;

-- GIN index on alternate_identifiers for future PIDINST-search queries
-- (e.g. find Facility by SerialNumber). Cheap to add now; covers the
-- common contains-query pattern.
CREATE INDEX proj_federation_facility_summary_alternate_identifiers_idx
    ON proj_federation_facility_summary
    USING GIN (alternate_identifiers);

-- Mutable read model. cora_app gets full CRUD; the projection writer
-- needs INSERT + UPDATE, and projection rebuilds need TRUNCATE / DELETE.
GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_federation_facility_summary TO cora_app;

-- Row-Level Security: defense-in-depth on federation tables.
-- SEC-FED-02 (per actor_profile precedent): every federation projection
-- table ENABLEs + FORCEs RLS with two flat cora_app policies so an
-- accidental owner-role bypass cannot leak cross-facility material.
-- The trust_anchor_credential_ids JSONB column is the explicit driver
-- (it binds CredentialIds to Facility rows when slice 6 populates it);
-- the rest of the row is non-sensitive Facility metadata. RLS gets
-- forced uniformly across the table for consistency with Permit /
-- Credential / Seal sibling tables.
ALTER TABLE proj_federation_facility_summary ENABLE ROW LEVEL SECURITY;
ALTER TABLE proj_federation_facility_summary FORCE  ROW LEVEL SECURITY;

CREATE POLICY proj_federation_facility_summary_cora_app_read
    ON proj_federation_facility_summary FOR SELECT
    TO cora_app
    USING (true);

CREATE POLICY proj_federation_facility_summary_cora_app_write
    ON proj_federation_facility_summary FOR ALL
    TO cora_app
    USING (true)
    WITH CHECK (true);

INSERT INTO projection_bookmarks (name)
VALUES ('proj_federation_facility_summary')
ON CONFLICT DO NOTHING;
