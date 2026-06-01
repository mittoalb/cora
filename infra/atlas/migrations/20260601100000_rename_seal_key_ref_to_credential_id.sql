-- Rename proj_federation_seal columns to match the post-2026-05-31
-- naming audit: `*_key_ref` -> `*_credential_id`.
--
-- The columns are UUID references to Credential aggregates; the
-- audit's R3 family-noun primacy + the project's `_id` suffix
-- convention call for `*_credential_id`. The `_ref` suffix stays
-- reserved across the codebase for non-UUID handles (Credential.
-- secret_ref: str = vault handle, Supply.monitor_ref: str | None,
-- Agent.model_ref: ModelRef custom VO). Of the ~33 UUID reference
-- fields in the codebase pre-audit, these two were the only
-- UUID-typed `_ref` fields; the rename closes the asymmetry.
--
-- Forward-only per project_forward_only_migrations.md. Federation
-- Seal landed 2026-05-30; the rename window is at its narrowest.
-- Once pilot data starts flowing, the column rename becomes a
-- production migration; today the table has effectively zero rows.
--
-- ## Three-step rename
--
-- ALTER TABLE ... RENAME COLUMN is atomic in PostgreSQL and cheap
-- against an empty (or near-empty) table. The CHECK constraint that
-- pins `online_key_ref != offline_key_ref` (key separation) must be
-- dropped + re-added with the new column names since the original
-- CHECK references the old column names by identifier.

ALTER TABLE proj_federation_seal
    RENAME COLUMN online_key_ref TO online_credential_id;

ALTER TABLE proj_federation_seal
    RENAME COLUMN offline_key_ref TO offline_credential_id;

-- Drop + re-add the key-separation CHECK constraint with the new
-- column names. The original constraint was named
-- `proj_federation_seal_keys_distinct` in the init migration.
ALTER TABLE proj_federation_seal
    DROP CONSTRAINT proj_federation_seal_keys_distinct;

ALTER TABLE proj_federation_seal
    ADD CONSTRAINT proj_federation_seal_credentials_distinct
        CHECK (online_credential_id != offline_credential_id);
