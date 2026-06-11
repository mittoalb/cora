-- Data BC: Distribution summary read model.
--
-- Folds the Distribution aggregate's genesis event into the
-- `proj_data_distribution_summary` read model used by future list / get
-- slices and by the Attestation projection-writer extension (per
-- [[project-data-distribution-design]] L27 + project-data-attestation-design
-- Slice C). Stage 1 ships ONE subscribed event (DistributionRegistered);
-- the Verified / Stale / Discarded transitions ship in follow-on slices,
-- and the columns are present day-one for additive future writes.
--
-- Subscribed events (apply order):
--   - DistributionRegistered  -> INSERT (status='Registered',
--                                        registered_at=occurred_at,
--                                        registered_by from payload)
--
-- Future event coverage (NAMED, NOT shipped Stage 1):
--   - DistributionVerified         -> UPDATE status='Verified'
--   - DistributionMarkedStale      -> UPDATE status='Stale'
--   - DistributionDiscarded        -> UPDATE status='Discarded'
--   - AttestationRecorded          -> projection-only status flip per
--                                     territory L7 (Attestation Slice C
--                                     extends this writer).
--
-- Identity:
--   - distribution_id (UUID): internal-opaque PK; UUIDv7 per cross-BC
--     identifier convention.
--
-- Cross-aggregate / cross-BC bindings (eventual-consistency primitives;
-- referential integrity enforced via decider-time pre-loads, NOT FKs):
--   - dataset_id (UUID): parent logical Dataset.
--   - supply_id  (UUID): storage-kind Supply hosting the bytes.
--
-- Byte-identical-copy invariants (decider-enforced; mirrored to the
-- projection for read-side convenience):
--   - checksum  (JSONB):     {algorithm: str, value: str}
--   - byte_size (BIGINT):    >= 0
--   - encoding  (JSONB):     {media_type: str, conforms_to: [str]}
--
-- Addressing:
--   - uri             (TEXT):  opaque URI string (s3://, file://, etc.)
--   - access_protocol (TEXT):  closed enum {HTTPS, Globus, S3, POSIX,
--                              NFS, OAI_PMH}
--
-- Structural invariants enforced at the DB tier:
--   - access_protocol is closed to the 6 enum values.
--   - status is closed to ('Registered', 'Verified', 'Stale', 'Discarded').
--   - UNIQUE INDEX on (dataset_id, supply_id, uri) PARTIAL WHERE
--     status != 'Discarded' captures the semantic "this Dataset has at
--     most one non-Discarded Distribution at this URI on this Supply".
--     Re-register after Discard is permitted. The UNIQUE collision is
--     handled writer-side per L31 (catch UniqueViolation, log WARN,
--     bookmark advances; mirrors Supply projection-writer precedent).

CREATE TABLE proj_data_distribution_summary (
    distribution_id     UUID         PRIMARY KEY,
    dataset_id          UUID         NOT NULL,
    supply_id           UUID         NOT NULL,
    uri                 TEXT         NOT NULL,
    checksum            JSONB        NOT NULL,
    byte_size           BIGINT       NOT NULL CHECK (byte_size >= 0),
    encoding            JSONB        NOT NULL,
    access_protocol     TEXT         NOT NULL CHECK (
        access_protocol IN ('HTTPS', 'Globus', 'S3', 'POSIX', 'NFS', 'OAI_PMH')
    ),
    status              TEXT         NOT NULL DEFAULT 'Registered' CHECK (
        status IN ('Registered', 'Verified', 'Stale', 'Discarded')
    ),

    registered_at       TIMESTAMPTZ  NOT NULL,
    registered_by       UUID         NOT NULL,
    verified_at         TIMESTAMPTZ,
    verified_by         UUID,
    marked_stale_at     TIMESTAMPTZ,
    marked_stale_by     UUID,
    discarded_at        TIMESTAMPTZ,
    discarded_by        UUID,
    discard_reason      TEXT,

    backfilled          BOOLEAN      NOT NULL DEFAULT FALSE,
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE proj_data_distribution_summary IS
    'Data Distribution summary read model. DCAT-3 dcat:Distribution materialization-tier; byte-identical copy of a Dataset at a storage-kind Supply. status FSM {Registered, Verified, Stale, Discarded} day-one; only Registered reachable in Stage 1.';
COMMENT ON COLUMN proj_data_distribution_summary.dataset_id IS
    'Parent logical Dataset. Eventual-consistency primitive: referential integrity is enforced by the decider-time Dataset pre-load, NOT a foreign key.';
COMMENT ON COLUMN proj_data_distribution_summary.supply_id IS
    'Storage-kind Supply hosting the bytes. Cross-BC binding via SupplyLookup port; referential integrity is enforced by the decider-time lookup, NOT a foreign key.';
COMMENT ON COLUMN proj_data_distribution_summary.checksum IS
    'Bulk-content integrity hash: {algorithm: str, value: str}. Must equal parent Dataset.checksum (byte-identical-copy invariant, decider-enforced).';
COMMENT ON COLUMN proj_data_distribution_summary.encoding IS
    'Encoding descriptor: {media_type: str, conforms_to: [str]}. conforms_to entries sorted deterministically on the event payload for byte-identical jsonb.';
COMMENT ON COLUMN proj_data_distribution_summary.backfilled IS
    'TRUE for rows synthesized by the Slice 2 lifespan-Python backfill from legacy Dataset.uri rows; FALSE for natively register_distribution-emitted rows. Future-cleanup marker; re-evaluate when Slice D drops Dataset.uri.';

-- Semantic uniqueness (per L22): this Dataset has at most one
-- non-Discarded Distribution at this URI on this Supply. Re-register
-- after Discard is permitted because the partial predicate excludes
-- Discarded rows. The UNIQUE collision is caught by the projection
-- writer (writer-side swallow per L31); the request always returns 201.
CREATE UNIQUE INDEX proj_data_distribution_summary_triple_uq
    ON proj_data_distribution_summary (dataset_id, supply_id, uri)
    WHERE status != 'Discarded';

-- Reverse-lookup queries: list every Distribution of a given Dataset.
CREATE INDEX proj_data_distribution_summary_dataset_idx
    ON proj_data_distribution_summary (dataset_id);

-- Profile-filter queries: find Distributions claiming conformance to a
-- given profile URI (NeXus, OME-Zarr, CIF, etc.).
CREATE INDEX proj_data_distribution_summary_conforms_to_idx
    ON proj_data_distribution_summary
    USING GIN ((encoding -> 'conforms_to'));

-- Mutable read model. cora_app gets full CRUD; the projection writer
-- needs INSERT + UPDATE, and projection rebuilds need TRUNCATE / DELETE.
GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_data_distribution_summary TO cora_app;

-- Row-Level Security: defense-in-depth uniform with sibling Data BC
-- projection tables. Two flat cora_app policies so an accidental
-- owner-role bypass cannot leak the URI + checksum payload, which
-- references storage-system addresses operators may treat as sensitive.
ALTER TABLE proj_data_distribution_summary ENABLE ROW LEVEL SECURITY;
ALTER TABLE proj_data_distribution_summary FORCE  ROW LEVEL SECURITY;

CREATE POLICY proj_data_distribution_summary_cora_app_read
    ON proj_data_distribution_summary FOR SELECT
    TO cora_app
    USING (true);

CREATE POLICY proj_data_distribution_summary_cora_app_write
    ON proj_data_distribution_summary FOR ALL
    TO cora_app
    USING (true)
    WITH CHECK (true);

INSERT INTO projection_bookmarks (name)
VALUES ('proj_data_distribution_summary')
ON CONFLICT DO NOTHING;
