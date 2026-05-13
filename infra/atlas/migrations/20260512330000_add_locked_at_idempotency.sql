-- Phase 9a: two-phase claim + 4xx error caching for idempotency_keys.
--
-- Today's table (migration 20260509170000) is single-phase: rows are
-- INSERT-on-completion via `ON CONFLICT DO NOTHING`. Phase 9a adds
-- in-flight tracking and error caching so retries get deterministic
-- responses even when:
--   - two retries arrive concurrently (one wins the claim, the other
--     gets a 409 + Retry-After: 1)
--   - the original handler raised a cacheable 4xx error (the cached
--     error is replayed on retry instead of re-running the handler)
--
-- ## Schema additions (all greenfield-friendly, no backfill needed)
--
--   - `locked_at TIMESTAMPTZ NULL` — null = completed; non-null =
--     in-flight, locked since this timestamp. Stale-lock recovery
--     (worker crashed mid-handler) is automatic via the
--     `idempotency_lock_stale_seconds` setting.
--   - `error_type TEXT NULL` + `error_msg TEXT NULL` — populated by
--     `finalize_error()` when a cacheable 4xx fires; null otherwise.
--   - `result` becomes NULLABLE (in-flight rows have no result yet;
--     completed-error rows have an error instead of a result). The
--     CHECK constraint below enforces the tri-state invariant.
--
-- ## Tri-state row invariant (CHECK constraint)
--
-- A row is exactly ONE of:
--   1. in-flight:       locked_at IS NOT NULL AND result IS NULL AND error_type IS NULL
--   2. completed-OK:    locked_at IS NULL AND result IS NOT NULL AND error_type IS NULL
--   3. completed-error: locked_at IS NULL AND result IS NULL AND error_type IS NOT NULL AND error_msg IS NOT NULL
--
-- Any other combination indicates a port / adapter bug; the CHECK
-- constraint surfaces it loudly at write time.
--
-- ## Index strategy
--
-- The hot read path is "claim or hit-check" against `(principal_id,
-- key)`. The existing PRIMARY KEY (principal_id, key) covers it.
-- Adding a partial index `WHERE locked_at IS NULL` would not help
-- given the PRIMARY KEY already lookups by the same columns; skip.
--
-- The TTL pruner (`DELETE FROM idempotency_keys WHERE created_at <
-- now() - interval 'N hours'`) uses the existing `created_at` index
-- (migration 20260509170000 line 30); no new index needed.
--
-- ## Forward-only
--
-- Per project_forward_only_migrations memory: this migration is
-- forward-only. No DOWN script. Rollback would be a NEW migration
-- that compensates (drop the columns, re-tighten NOT NULL on result).
--
-- Atlas safety scan blocks DROP TABLE / DROP COLUMN / TRUNCATE /
-- ALTER COLUMN ... TYPE. We use ADD COLUMN and ALTER COLUMN ... DROP
-- NOT NULL — neither is forbidden. No safety opt-out comment needed.

ALTER TABLE idempotency_keys
    ADD COLUMN locked_at  TIMESTAMPTZ NULL,
    ADD COLUMN error_type TEXT NULL,
    ADD COLUMN error_msg  TEXT NULL,
    ALTER COLUMN result DROP NOT NULL;

ALTER TABLE idempotency_keys
    ADD CONSTRAINT idempotency_keys_state_chk CHECK (
        (locked_at IS NOT NULL AND result IS NULL AND error_type IS NULL)
        OR (locked_at IS NULL AND result IS NOT NULL AND error_type IS NULL)
        OR (
            locked_at IS NULL
            AND result IS NULL
            AND error_type IS NOT NULL
            AND error_msg IS NOT NULL
        )
    );
