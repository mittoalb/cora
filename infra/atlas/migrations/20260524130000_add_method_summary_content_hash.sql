-- Adds proj_recipe_method_summary.content_hash for Candidate A
-- (content-addressed identity) Method adoption.
--
-- Per project_content_addressed_identity_design, MethodVersioned now
-- carries a SHA-256 over the Method's content subset (name +
-- parameters_schema + capability_id + needed_families +
-- needed_supplies), captured in the event payload by the decider per
-- the non-determinism principle and projected here so equivalence
-- lookups (Candidate G cherry-pick analogue, BCO etag export,
-- Workflow-RO-Crate ControlAction binding) can scan the read model
-- without folding history.
--
-- NULL-able + additive: pre-rollout MethodVersioned events have no
-- content_hash field on the payload; the projection leaves the
-- column NULL for those rows (matches aggregate-state semantics where
-- pre-rollout methods carry `content_hash: str | None = None`). No
-- backfill per project_forward_only_migrations.
--
-- Index covers the equivalence-query shape `WHERE content_hash = $1`
-- expected from cherry-pick / etag lookup callers. Partial index on
-- non-NULL keeps pre-rollout rows out of the b-tree.

ALTER TABLE proj_recipe_method_summary
    ADD COLUMN content_hash TEXT;

CREATE INDEX ix_proj_recipe_method_summary_content_hash
    ON proj_recipe_method_summary (content_hash)
    WHERE content_hash IS NOT NULL;
