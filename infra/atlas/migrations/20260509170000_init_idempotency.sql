-- Idempotency-Key store.
--
-- Backs the cross-BC idempotency decorator
-- (`cora.access._idempotency.with_idempotency`). On retry with the
-- same `(principal_id, key)`, the cached result is returned and the
-- command does not re-execute.
--
-- Composite primary key on (principal_id, key) namespaces by principal
-- so different callers can use the same idempotency-key without
-- collision. INSERT ... ON CONFLICT DO NOTHING is the application-side
-- pattern for first-writer-wins under concurrent writes.
--
-- Phase 2d ships single-phase semantics (get + put). Production
-- two-phase ("in_progress" claim then "completed" update) per the
-- Stripe pattern is deferred until concurrent-retry load surfaces.
--
-- The `created_at` index supports a future TTL cleanup job (Stripe
-- prunes keys older than 24 hours).

CREATE TABLE idempotency_keys (
    principal_id   uuid        NOT NULL,
    key            text        NOT NULL,
    command_hash   text        NOT NULL,
    command_name   text        NOT NULL,
    result         jsonb       NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (principal_id, key)
);

CREATE INDEX idempotency_keys_created_at_idx ON idempotency_keys (created_at);
