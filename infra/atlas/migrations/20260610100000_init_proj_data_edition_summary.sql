-- Data BC: Edition summary read model.
--
-- Folds the Edition aggregate's 6-event lifecycle into the
-- `proj_data_edition_summary` read model used by future list / get
-- slices and citation-export adapters. Stage 1 ships all 6 event
-- subscriptions across slices A-E; this initial migration carries
-- the table + all nullable transition columns + indexes + RLS day
-- one, per the additive-state pattern (mirrors Distribution Slice A
-- precedent + Supply Slice 7B precedent). Subsequent slices add
-- projection-writer Python code only; ZERO new Atlas migrations
-- across slices B / C / D / E.
--
-- Subscribed events (across the 5 slices):
--   - EditionRegistered      -> INSERT (status='Registered',
--                                       registered_at, registered_by,
--                                       creators, dataset_ids,
--                                       initial publisher / license / year)
--   - EditionDatasetAdded    -> UPDATE dataset_ids (array_append)
--   - EditionDatasetRemoved  -> UPDATE dataset_ids (array_remove)
--   - EditionSealed          -> UPDATE status='Sealed', content_hash,
--                                       sealed_at, sealed_by,
--                                       publisher_facility_code,
--                                       publication_year, license
--   - EditionPublished       -> UPDATE status='Published',
--                                       external_pid_scheme,
--                                       external_pid_value,
--                                       published_content_hash,
--                                       published_at, published_by
--   - EditionWithdrawn       -> UPDATE status='Withdrawn',
--                                       withdrawn_at, withdrawn_by,
--                                       withdrawal_reason
--
-- Identity:
--   - edition_id (UUID): internal-opaque PK; UUIDv7 per cross-BC
--     identifier convention.
--
-- Set-semantic member field:
--   - dataset_ids (UUID[]): mutated by Add / Remove during Registered;
--     frozen at Sealed (the EditionSealed event payload's
--     sealed_dataset_ids becomes the immutability anchor).
--
-- Two-content-hash model:
--   - content_hash:           sha256 set ONCE at Sealed; immutable.
--   - published_content_hash: sha256 of re-serialized post-DOI bytes
--                             set at Published; distinct from content_hash
--                             by design (DOI bake invalidates the sealed
--                             hash). Both denormalized for read-side
--                             convenience.
--
-- Structural invariants enforced at the DB tier:
--   - kind closed to the 6 EditionKind values
--   - status closed to the 4 EditionStatus values

CREATE TABLE proj_data_edition_summary (
    edition_id              UUID         PRIMARY KEY,
    kind                    TEXT         NOT NULL CHECK (
        kind IN ('ROCrate', 'DataCite', 'Croissant', 'OAIS_AIP', 'OAIS_DIP', 'NeXus')
    ),
    title                   TEXT         NOT NULL,
    dataset_ids             UUID[]       NOT NULL DEFAULT '{}',
    creators                JSONB        NOT NULL DEFAULT '[]'::jsonb,
    license                 TEXT,
    publication_year        INT,
    publisher_facility_code TEXT,
    content_hash            TEXT,
    published_content_hash  TEXT,
    external_pid_scheme     TEXT,
    external_pid_value      TEXT,
    status                  TEXT         NOT NULL DEFAULT 'Registered' CHECK (
        status IN ('Registered', 'Sealed', 'Published', 'Withdrawn')
    ),

    registered_at           TIMESTAMPTZ  NOT NULL,
    registered_by           UUID         NOT NULL,
    sealed_at               TIMESTAMPTZ,
    sealed_by               UUID,
    published_at            TIMESTAMPTZ,
    published_by            UUID,
    withdrawn_at            TIMESTAMPTZ,
    withdrawn_by            UUID,
    withdrawal_reason       TEXT,

    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE proj_data_edition_summary IS
    'Data Edition summary read model. ISBD / FRBR / BIBFRAME publication-tier; citable publication-package over a frozen set of Production-intent Datasets. status FSM {Registered, Sealed, Published, Withdrawn} day-one with all 4 states reachable across slices A-E.';
COMMENT ON COLUMN proj_data_edition_summary.dataset_ids IS
    'Member Dataset ids. Mutated by Add / Remove during Registered; frozen at Sealed (the EditionSealed event payload sealed_dataset_ids is the immutability anchor).';
COMMENT ON COLUMN proj_data_edition_summary.creators IS
    'Ordered list of {actor_id, affiliation} objects. Order is publication-significant (first-author convention); NEVER sorted on wire.';
COMMENT ON COLUMN proj_data_edition_summary.content_hash IS
    'sha256 of the pre-DOI serializer output. Set ONCE at the Sealed transition; immutable thereafter on the aggregate state. Anchors the operator commit to shape + membership.';
COMMENT ON COLUMN proj_data_edition_summary.published_content_hash IS
    'sha256 of the re-serialized post-DOI bytes. Distinct from content_hash by design (DOI bake invalidates the sealed hash). Anchors the cited artifact bytes.';
COMMENT ON COLUMN proj_data_edition_summary.publisher_facility_code IS
    'Publisher Facility code (cross-deployment convergent slug). FacilityLookup-resolved at the seal handler; bare TEXT here per the wire-payload bare-str convention.';

-- Listing queries by (status, kind): the most common filter combo
-- for citation-management UIs.
CREATE INDEX proj_data_edition_summary_status_kind_idx
    ON proj_data_edition_summary (status, kind);

-- Reverse-lookup queries: "list every Edition that contains Dataset X".
CREATE INDEX proj_data_edition_summary_dataset_ids_idx
    ON proj_data_edition_summary USING GIN (dataset_ids);

-- Facility-scoped queries: list Editions published from a given Facility.
CREATE INDEX proj_data_edition_summary_publisher_facility_code_idx
    ON proj_data_edition_summary (publisher_facility_code);

-- Mutable read model. cora_app gets full CRUD; the projection writer
-- needs INSERT + UPDATE, and projection rebuilds need TRUNCATE / DELETE.
GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_data_edition_summary TO cora_app;

-- Row-Level Security: defense-in-depth uniform with sibling Data BC
-- projection tables. Two flat cora_app policies so an accidental
-- owner-role bypass cannot leak the citation payload, which references
-- publisher / creators that may be subject to per-Facility disclosure
-- policy.
ALTER TABLE proj_data_edition_summary ENABLE ROW LEVEL SECURITY;
ALTER TABLE proj_data_edition_summary FORCE  ROW LEVEL SECURITY;

CREATE POLICY proj_data_edition_summary_cora_app_read
    ON proj_data_edition_summary FOR SELECT
    TO cora_app
    USING (true);

CREATE POLICY proj_data_edition_summary_cora_app_write
    ON proj_data_edition_summary FOR ALL
    TO cora_app
    USING (true)
    WITH CHECK (true);

INSERT INTO projection_bookmarks (name)
VALUES ('proj_data_edition_summary')
ON CONFLICT DO NOTHING;
