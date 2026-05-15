-- Phase 10a-a iter 4: Supply BC's first projection — supply summary.
--
-- Folds the Supply aggregate's lifecycle events into the
-- `proj_supply_summary` read model used by the `list_supplies`
-- slice for `GET /supplies` keyset-paginated list endpoint with
-- optional scope / kind / status filters.
--
-- Subscribed events (10a-a):
--   - SupplyRegistered      -> INSERT (status='Unknown', last_status_*=NULL)
--   - SupplyMarkedAvailable -> UPDATE status='Available' + last_status_changed_at
--                                     + last_status_reason + last_trigger
--
-- Phase 10a-b will subscribe to 4 more transitions (SupplyDegraded /
-- SupplyMarkedUnavailable / SupplyMarkedRecovering / SupplyRestored).
-- Each updates status + the same audit triple. The CHECK constraints
-- on `status` and `last_trigger` are locked with the full enum values
-- day one (5 statuses + 3 triggers) so 10a-b's transitions land
-- without a constraint migration.
--
-- ## Identity: stable opaque + typed address
--
-- `supply_id` is the stable opaque handle (UUID PK). `(scope, kind,
-- name)` is the operator-readable address; UNIQUE INDEX enforces
-- cross-stream uniqueness at projection-insert time (the aggregate
-- cannot enforce cross-stream invariants without DCB per
-- project_deferred). On duplicate registration, the second insert
-- fails at the projection layer; operators de-register one via the
-- future deregister_supply slice.
--
-- ## Audit columns
--
-- `last_status_changed_at` / `last_status_reason` / `last_trigger`
-- are nullable until the supply transitions out of `Unknown`. They
-- denormalize the latest transition's audit metadata for at-a-glance
-- ops queries ("show me supplies that went Available recently and
-- why"). Same precedent as proj_decision_summary's confidence_band
-- denormalized at INSERT.
--
-- ## Pagination index
--
-- Keyset pagination on `(registered_at, supply_id)`. `registered_at`
-- is set once at SupplyRegistered (immutable), so it's a stable
-- keyset key. Cursor in the API encodes `(registered_at, supply_id)`.
-- Per-filter B-tree indexes on `(scope)` / `(kind)` / `(status)` are
-- deferred per 8e precedent: revisit when a slow-query incident
-- surfaces (low-cardinality columns rarely benefit from a btree).
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_supply_summary (
    supply_id              UUID        PRIMARY KEY,
    scope                  TEXT        NOT NULL CHECK (
        scope IN ('Facility', 'Sector', 'Beamline')
    ),
    kind                   TEXT        NOT NULL,
    name                   TEXT        NOT NULL,
    status                 TEXT        NOT NULL CHECK (
        status IN ('Unknown', 'Available', 'Degraded', 'Unavailable', 'Recovering')
    ),
    registered_at          TIMESTAMPTZ NOT NULL,
    last_status_changed_at TIMESTAMPTZ,
    last_status_reason     TEXT,
    last_trigger           TEXT        CHECK (
        last_trigger IS NULL OR last_trigger IN ('Operator', 'Monitor', 'Auto')
    ),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX proj_supply_summary_address_uq
    ON proj_supply_summary (scope, kind, name);

CREATE INDEX proj_supply_summary_keyset_idx
    ON proj_supply_summary (registered_at, supply_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_supply_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_supply_summary')
ON CONFLICT DO NOTHING;
