-- Safety BC: replace Clearance.kind StrEnum with template_id FK to ClearanceTemplate.
--
-- The kind column (Form9 / ESAF / SAF / DUO / ...) is replaced by
-- template_id (UUID) referencing proj_safety_clearance_template_summary,
-- plus a denormalized template_code (TEXT) for list-view display and
-- filtering. The (facility_code, code) address pair on the template
-- summary is the source of truth; carrying template_code on the Clearance
-- row avoids a per-row join at list time.
--
-- The deterministic template_id derivation
--   uuid5(_SAFETY_CLEARANCE_TEMPLATE_NAMESPACE, f"{facility_code}:{kind}")
-- matches the Slice 9C auto-seed lifespan hook, so re-INSERT through the
-- projection worker after this migration produces the same UUIDs the
-- seeded ClearanceTemplate rows hold.
--
-- ## Reset + replay
--
-- The new columns are NOT NULL. uuid5 is not in PostgreSQL core (uuid-ossp
-- and pgcrypto are not loaded as extensions in this project), so a pure-SQL
-- backfill is not available. Same pattern as
-- 20260601100200_add_proj_federation_seal_summary_stream_id.sql: the
-- projection is a derived read model, the event store is the source of
-- truth, so we DELETE the rows + reset the bookmark and let the worker
-- re-INSERT every row with the new columns populated from the 9E-extended
-- ClearanceRegistered payload. Greenfield (pre-pilot): the row count is
-- effectively zero; the DELETE is belt-and-suspenders.
--
-- Forward-only per project_forward_only_migrations.md.

ALTER TABLE proj_safety_clearance_summary
    ADD COLUMN template_id UUID,
    ADD COLUMN template_code TEXT;

DELETE FROM proj_safety_clearance_summary;

UPDATE projection_bookmarks
    SET last_transaction_id = '0'::xid8,
        last_position = 0,
        updated_at = now()
    WHERE name = 'proj_safety_clearance_summary';

ALTER TABLE proj_safety_clearance_summary
    ALTER COLUMN template_id SET NOT NULL,
    ALTER COLUMN template_code SET NOT NULL;

ALTER TABLE proj_safety_clearance_summary
    DROP COLUMN kind;

CREATE INDEX proj_safety_clearance_summary_template_id_idx
    ON proj_safety_clearance_summary (template_id);
