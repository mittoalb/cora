-- Widen `proj_supply_summary` for the `deregister_supply` slice:
--   1. CHECK constraint on `status` adds `'Decommissioned'`.
--   2. `proj_supply_summary_address_uq` UNIQUE INDEX becomes PARTIAL
--      on `WHERE status != 'Decommissioned'`, so a deregistered
--      Supply does not block re-registration of the same
--      `(scope, kind, name)` address.
--
-- Original migration (20260514100000) pinned `status IN (5 health
-- values)` and used an unconditional UNIQUE INDEX on (scope, kind,
-- name). [[project_deregister_supply_design]] introduces a 6th
-- lifecycle-terminal status `Decommissioned` and the operator escape
-- hatch `deregister_supply`. Both schema changes are required for the
-- design's locked behavior:
--
--   - Without (1), `SupplyDeregistered` projection writes fail with
--     `asyncpg.CheckViolationError` and the worker stalls.
--   - Without (2), re-registering at the same address after a
--     deregister fails with `asyncpg.UniqueViolationError` because
--     the Decommissioned row holds the slot forever.
--
-- Forward-only per [[project_forward_only_migrations]]. CHECK widening
-- is fast at pilot volume: PG still scans the table to validate the
-- new constraint, but the new set is a STRICT SUPERSET of the old set
-- so every existing row's `status` value passes. The UNIQUE INDEX swap
-- is `DROP INDEX` + `CREATE UNIQUE INDEX ... WHERE`; PG supports
-- partial unique indexes natively.
--
-- ## Deployment ordering (load-bearing)
--
-- This migration MUST land before the application code that emits
-- `SupplyDeregistered`. The OLD status CHECK rejects 'Decommissioned',
-- and the new projection writer would stall the worker on the first
-- such event. The OLD writer-against-NEW-schema direction is safe
-- (new CHECK accepts every value the old code writes).
--
-- Atlas safety: ALTER TABLE ... DROP CONSTRAINT + ADD CONSTRAINT and
-- DROP INDEX + CREATE UNIQUE INDEX are not on Atlas's forbidden-DDL
-- list. No `--atlas:nolint` opt-out needed. The DROP INDEX briefly
-- removes uniqueness enforcement; pre-existing Decommissioned rows
-- cannot exist yet (this migration is the first time the value is
-- accepted), so the swap is safe.

ALTER TABLE proj_supply_summary
    DROP CONSTRAINT proj_supply_summary_status_check;

ALTER TABLE proj_supply_summary
    ADD CONSTRAINT proj_supply_summary_status_check
        CHECK (status IN (
            'Unknown',
            'Available',
            'Degraded',
            'Unavailable',
            'Recovering',
            'Decommissioned'
        ));

DROP INDEX proj_supply_summary_address_uq;

CREATE UNIQUE INDEX proj_supply_summary_address_uq
    ON proj_supply_summary (scope, kind, name)
    WHERE status != 'Decommissioned';
