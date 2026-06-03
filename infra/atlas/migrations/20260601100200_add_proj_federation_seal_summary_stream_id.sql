-- Federation BC: back the Seal summary cursor with a real column.
--
-- The list_seals slice keys cursor pagination on a UUID derived from
-- facility_id via uuid5 over a fixed namespace (see
-- cora.federation.aggregates.seal._stream_id.seal_stream_id). The
-- init migration created the projection with facility_id (TEXT) as
-- the PK and no UUID column; the list-query factory bound that UUID
-- against the TEXT facility_id column and asyncpg rejected the type
-- mismatch (`DataError: invalid input for query argument $4: UUID(...)
-- expected str, got UUID`).
--
-- This migration mirrors every other federation list_* slice
-- (list_credentials.credential_id, list_permits.permit_id, ...) by
-- physically backing the cursor anchor with a UUID column. The
-- projection populates it at INSERT time from the same Python uuid5
-- derivation; the handler then drops the seal_stream_id() call at
-- cursor time and binds UUID against UUID.
--
-- ## Reset + replay
--
-- The new column is NOT NULL, so existing rows must either be
-- backfilled or removed. uuid5 is not in PostgreSQL core (uuid-ossp
-- and pgcrypto are not loaded as extensions in this project) so a
-- pure-SQL backfill is not available. The projection is a derived
-- read model and the event store is the source of truth; we reset the
-- bookmark and let the worker re-INSERT every row with the new column
-- populated. Federation Seal landed 2026-05-30 so the row count is
-- effectively zero; the DELETE is belt-and-suspenders for safety.
--
-- Forward-only per project_forward_only_migrations.md. The Atlas
-- safety scanner does not block ALTER TABLE ... ADD COLUMN, DELETE,
-- UPDATE on projection_bookmarks, or ADD CONSTRAINT.
--
-- ## RLS posture re-assertion
--
-- SEC-FED-02 (test_federation_projections_rls_force.py) requires
-- every `proj_federation_*` migration to re-state ENABLE + FORCE
-- row-level-security and two cora_app policies (read + write). The
-- guard is mechanical and catches the case where a future ALTER
-- migration loses the RLS posture during a rebase. ENABLE / FORCE
-- are idempotent on PostgreSQL; the policies are re-created with
-- DROP IF EXISTS + CREATE for the same reason. The locked posture
-- mirrors 20260530210200_init_proj_federation_seal_summary.sql.

ALTER TABLE proj_federation_seal_summary
    ADD COLUMN seal_stream_id UUID;

DELETE FROM proj_federation_seal_summary;

UPDATE projection_bookmarks
    SET last_transaction_id = '0'::xid8,
        last_position = 0,
        updated_at = now()
    WHERE name = 'proj_federation_seal_summary';

ALTER TABLE proj_federation_seal_summary
    ALTER COLUMN seal_stream_id SET NOT NULL;

ALTER TABLE proj_federation_seal_summary
    ADD CONSTRAINT proj_federation_seal_summary_stream_id_unique
        UNIQUE (seal_stream_id);

CREATE INDEX proj_federation_seal_summary_stream_id_idx
    ON proj_federation_seal_summary (initialized_at, seal_stream_id);

ALTER TABLE proj_federation_seal_summary ENABLE ROW LEVEL SECURITY;
ALTER TABLE proj_federation_seal_summary FORCE  ROW LEVEL SECURITY;

DROP POLICY IF EXISTS proj_federation_seal_summary_cora_app_read
    ON proj_federation_seal_summary;
CREATE POLICY proj_federation_seal_summary_cora_app_read
    ON proj_federation_seal_summary FOR SELECT
    TO cora_app
    USING (true);

DROP POLICY IF EXISTS proj_federation_seal_summary_cora_app_write
    ON proj_federation_seal_summary;
CREATE POLICY proj_federation_seal_summary_cora_app_write
    ON proj_federation_seal_summary FOR ALL
    TO cora_app
    USING (true)
    WITH CHECK (true);
