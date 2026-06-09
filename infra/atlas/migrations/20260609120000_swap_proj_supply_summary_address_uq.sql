-- Session 5 Slice 7C: swap the proj_supply_summary UNIQUE INDEX to
-- compose `facility_code` + `containing_asset_id` into the address
-- tuple, replacing the original `(scope, kind, name)` tuple.
--
-- This closes the transitional intermediate state introduced by Slice
-- 7A (facility_code added, index not yet swapped) and Slice 7B
-- (containing_asset_id added, index not yet swapped): two facilities
-- co-registering the same `(kind, name)` at the same `scope` used to
-- collide in the projection's UniqueViolation-swallow fallback.
-- After this slice, two facilities can each own a Beamline-scope
-- `(LiquidNitrogen, "2-BM LN2 dewar")` row, and within one facility
-- two distinct containing-Asset bindings can each own the same
-- `(kind, name)` pair (a per-beamline LN2 dewar at one Asset vs a
-- sector-wide manifold at another Asset).
--
-- ## Three coordinated changes
--
--   1. Tighten `facility_code` to NOT NULL. The projection writer
--      always provides a value (Slice 7A introduced the column
--      nullable as a safety net; the writer never emits NULL). Pre-
--      pilot greenfield: no rows can have NULL, so the constraint
--      tightening is a no-op against actual data.
--   2. DROP the existing UNIQUE INDEX on `(scope, kind, name)`.
--      Slice 7E will drop the `scope` column entirely as part of
--      the SupplyScope retirement; this slice keeps the column intact
--      but removes its uniqueness role.
--   3. CREATE the new PARTIAL UNIQUE INDEX. The index expression uses
--      `COALESCE(containing_asset_id::text, '')` so facility-scope
--      Supplies (NULL containing_asset_id) share a sentinel key per
--      facility and still enforce per-(facility_code, kind, name)
--      uniqueness; non-facility-scope Supplies use the typed UUID
--      stringified into the key. The PARTIAL predicate stays on
--      `WHERE status != 'Decommissioned'` (slice
--      `20260527160000_widen_proj_supply_summary_for_deregister`
--      precedent) so the operator-escape-hatch re-registration story
--      for the disposition memo's Option A continues to hold.
--
-- Forward-only per [[project_forward_only_migrations]]. NULL-tightening
-- is fast at pilot volume because the projection writer never emitted
-- NULL; PG scans + validates without rewriting rows. DROP / CREATE
-- INDEX briefly removes uniqueness enforcement during the swap; with
-- the pre-pilot deployment volume the gap is sub-millisecond.
--
-- ## Deployment ordering (load-bearing)
--
-- This migration MUST land before any deployment that REGISTERS two
-- Supplies at the same (scope, kind, name) but different
-- (facility_code, containing_asset_id): the OLD index would reject
-- the second one. In the current pre-pilot footprint no such
-- registration is planned, so ordering against application code is
-- relaxed. Atlas safety: ALTER COLUMN SET NOT NULL + DROP INDEX +
-- CREATE UNIQUE INDEX (functional expression) are all allowed; no
-- `--atlas:nolint` opt-out needed.
--
-- ## Non-unique containing_asset_id lookup index
--
-- Slice 7D will expose `?containing_asset_id=` as a list-endpoint
-- filter, which needs a non-unique B-tree index for predicate
-- pushdown. The Slice 7B migration's docstring promised this index
-- would land in Slice 7C; we add it here as a PARTIAL index on
-- `WHERE containing_asset_id IS NOT NULL` (facility-scope rows
-- never appear in `?containing_asset_id=` queries; the partial
-- predicate keeps the index narrow).

ALTER TABLE proj_supply_summary
    ALTER COLUMN facility_code SET NOT NULL;

DROP INDEX proj_supply_summary_address_uq;

CREATE UNIQUE INDEX proj_supply_summary_address_uq
    ON proj_supply_summary (
        facility_code,
        COALESCE(containing_asset_id::text, ''),
        kind,
        name
    )
    WHERE status != 'Decommissioned';

CREATE INDEX proj_supply_summary_containing_asset_id_idx
    ON proj_supply_summary (containing_asset_id)
    WHERE containing_asset_id IS NOT NULL;
