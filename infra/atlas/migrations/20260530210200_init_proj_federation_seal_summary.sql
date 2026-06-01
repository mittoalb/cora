-- Federation BC: Seal summary projection.
--
-- Singleton-per-facility table that folds the Seal aggregate's
-- lifecycle events into a current-state view of the facility's signing
-- chain. One row per facility; facility_id is both PK and (per the
-- aggregate's design) the natural identity tuple.
--
-- Subscribed events (apply order):
--   - SealInitialized         -> INSERT (status='Live',
--                                        current_sequence_number=0,
--                                        initialized_at=occurred_at,
--                                        last_signed_at=NULL)
--   - PointerSigned           -> UPDATE current_head_hash,
--                                       current_sequence_number,
--                                       last_signed_by_actor_id,
--                                       last_signed_at=occurred_at
--   - OnlineKeyRotated        -> UPDATE online_key_ref
--   - RepublishingStarted     -> UPDATE status='Republishing'
--   - RepublishingCompleted   -> UPDATE status='Live'
--
-- Online vs offline key separation: the offline key is the recovery
-- root; the online key is the day-to-day signing key. They must never
-- be the same value (a DB-level CHECK enforces this; the aggregate
-- enforces it at write time).

CREATE TABLE proj_federation_seal_summary (
    facility_id                 TEXT        PRIMARY KEY,
    online_key_ref              UUID        NOT NULL,
    offline_key_ref             UUID        NOT NULL,
    current_head_hash           TEXT,
    current_sequence_number     BIGINT      NOT NULL DEFAULT 0
        CHECK (current_sequence_number >= 0),
    initialized_by_actor_id     UUID        NOT NULL,
    last_signed_by_actor_id     UUID,
    status                      TEXT        NOT NULL CHECK (
        status IN ('Live', 'Republishing')
    ),

    initialized_at              TIMESTAMPTZ NOT NULL,
    last_signed_at              TIMESTAMPTZ,
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT proj_federation_seal_summary_singleton_per_facility
        UNIQUE (facility_id),
    CONSTRAINT proj_federation_seal_summary_keys_distinct
        CHECK (online_key_ref != offline_key_ref)
);

COMMENT ON TABLE proj_federation_seal_summary IS
    'Singleton-per-facility signing-chain head. One row per facility (PK + redundant UNIQUE for documentation).';

-- Hot-path filter: facilities currently republishing (background
-- worker checks this on a schedule).
CREATE INDEX proj_federation_seal_summary_status_idx
    ON proj_federation_seal_summary (status);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_federation_seal_summary TO cora_app;

-- Row-Level Security: defense-in-depth on signing-chain head.
ALTER TABLE proj_federation_seal_summary ENABLE ROW LEVEL SECURITY;
ALTER TABLE proj_federation_seal_summary FORCE  ROW LEVEL SECURITY;

CREATE POLICY proj_federation_seal_summary_cora_app_read
    ON proj_federation_seal_summary FOR SELECT
    TO cora_app
    USING (true);

CREATE POLICY proj_federation_seal_summary_cora_app_write
    ON proj_federation_seal_summary FOR ALL
    TO cora_app
    USING (true)
    WITH CHECK (true);

INSERT INTO projection_bookmarks (name)
VALUES ('proj_federation_seal_summary')
ON CONFLICT DO NOTHING;
