-- Data BC: Attestation summary read model.
--
-- Folds the Attestation aggregate's single AttestationRecorded event
-- (genesis-and-terminal) into the `proj_data_attestation_summary` read
-- model used by future list / get slices and by the projection-side
-- Distribution.status flip (the Distribution projection writer
-- extension subscribes to AttestationRecorded and writes
-- `proj_data_distribution_summary.status` to 'Verified' / 'Stale' per
-- territory L7).
--
-- Subscribed events (apply order):
--   - AttestationRecorded -> INSERT (always; terminal-at-genesis)
--
-- Identity:
--   - attestation_id (UUID): internal-opaque PK; UUIDv7 per cross-BC
--     identifier convention. The Attestation stream uses the same UUID
--     as the stream id (L19; no uuid5 derivation).
--
-- Cross-aggregate bindings (eventual-consistency primitives; referential
-- integrity enforced via decider-time pre-loads, NOT FKs):
--   - dataset_id      (UUID NOT NULL): always present.
--   - distribution_id (UUID NULL):     required for byte-level kinds
--                                      (ChecksumVerified / FormatValidated /
--                                      BitRotChecked); NULL for
--                                      ConformsToValidated.
--
-- Closed enums (mirrored at the DB tier for defense-in-depth):
--   - kind:    {ChecksumVerified, FormatValidated, ConformsToValidated,
--               BitRotChecked}
--   - outcome: {Match, Mismatch, Unreachable}
--
-- Discriminated evidence:
--   - evidence (JSONB NOT NULL): nested object whose shape is
--     discriminated by the sibling `kind` field. Today only the
--     ChecksumVerified shape is concrete:
--       {algorithm: str, value: str | null, verifier_supply_id: str,
--        verifier_kind: str, error_detail?: str}
--
-- Fold-symmetry attribution per [[project_fold_symmetry_design]]:
--   - attested_at (TIMESTAMPTZ NOT NULL): WHEN the fact was recorded.
--   - attested_by (UUID NOT NULL):        WHO recorded it.
--
-- Indexes:
--   - (dataset_id, attested_at DESC):     "latest Attestations for this
--                                          Dataset".
--   - (distribution_id, attested_at DESC) PARTIAL WHERE distribution_id
--     IS NOT NULL: "latest Attestations for this Distribution" (the
--     Distribution projection-writer extension reads this for the
--     status flip).
--   - (kind, outcome): general analytics; verifier-rate dashboards,
--     daily-cron-bit-rot fact-finding.

CREATE TABLE proj_data_attestation_summary (
    attestation_id   UUID         PRIMARY KEY,
    dataset_id       UUID         NOT NULL,
    distribution_id  UUID         NULL,
    kind             TEXT         NOT NULL CHECK (
        kind IN ('ChecksumVerified', 'FormatValidated',
                 'ConformsToValidated', 'BitRotChecked')
    ),
    outcome          TEXT         NOT NULL CHECK (
        outcome IN ('Match', 'Mismatch', 'Unreachable')
    ),
    evidence         JSONB        NOT NULL,
    attested_at      TIMESTAMPTZ  NOT NULL,
    attested_by      UUID         NOT NULL,

    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE proj_data_attestation_summary IS
    'Data Attestation summary read model. Terminal-at-genesis fact-chain (one stream per Attestation). Used by future list / get slices and by the Distribution projection writer extension that flips Distribution.status on ChecksumVerified Match/Mismatch outcomes.';
COMMENT ON COLUMN proj_data_attestation_summary.dataset_id IS
    'Parent logical Dataset (always required). Eventual-consistency primitive: referential integrity is enforced by the decider-time Dataset pre-load, NOT a foreign key.';
COMMENT ON COLUMN proj_data_attestation_summary.distribution_id IS
    'Optional Distribution byte-copy. Required for byte-level kinds (ChecksumVerified, FormatValidated, BitRotChecked); NULL for ConformsToValidated. Enforced by the decider, mirrored here for read-side convenience.';
COMMENT ON COLUMN proj_data_attestation_summary.evidence IS
    'Discriminated evidence object whose shape is gated by the sibling `kind`. ChecksumVerified shape: {algorithm, value, verifier_supply_id, verifier_kind, error_detail?}.';

-- Reverse-lookup queries: latest Attestations for a given Dataset.
CREATE INDEX proj_data_attestation_summary_dataset_idx
    ON proj_data_attestation_summary (dataset_id, attested_at DESC);

-- Reverse-lookup queries: latest Attestations for a given Distribution.
-- Partial PARTIAL WHERE distribution_id IS NOT NULL keeps the index
-- skinny (ConformsToValidated rows do not bind a Distribution).
CREATE INDEX proj_data_attestation_summary_distribution_idx
    ON proj_data_attestation_summary (distribution_id, attested_at DESC)
    WHERE distribution_id IS NOT NULL;

-- Analytics queries: verifier-outcome rate dashboards, bit-rot trends.
CREATE INDEX proj_data_attestation_summary_kind_outcome_idx
    ON proj_data_attestation_summary (kind, outcome);

-- Mutable read model. cora_app gets full CRUD; the projection writer
-- only INSERTs (terminal-at-genesis), and projection rebuilds need
-- TRUNCATE / DELETE.
GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_data_attestation_summary TO cora_app;

-- Row-Level Security: defense-in-depth uniform with sibling Data BC
-- projection tables.
ALTER TABLE proj_data_attestation_summary ENABLE ROW LEVEL SECURITY;
ALTER TABLE proj_data_attestation_summary FORCE  ROW LEVEL SECURITY;

CREATE POLICY proj_data_attestation_summary_cora_app_read
    ON proj_data_attestation_summary FOR SELECT
    TO cora_app
    USING (true);

CREATE POLICY proj_data_attestation_summary_cora_app_write
    ON proj_data_attestation_summary FOR ALL
    TO cora_app
    USING (true)
    WITH CHECK (true);

INSERT INTO projection_bookmarks (name)
VALUES ('proj_data_attestation_summary')
ON CONFLICT DO NOTHING;
