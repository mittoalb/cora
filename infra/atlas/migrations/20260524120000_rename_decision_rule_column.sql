-- Cluster 2 of the 2026-05-22 cross-package consistency audit: rename
-- the Decision projection's `decision_rule` column to `rule`. The
-- compound "decision_rule" repeats the aggregate name in a field name
-- on the aggregate's own projection, violating the locked R3 rule
-- (Google AIP-140 + Vaughn Vernon's IDDD precedent: bare field names
-- inside an aggregate's own context). Same rename happens at the
-- aggregate-state / event-payload / handler / route / tool layers in
-- the source tree; this migration brings the projection column in
-- lockstep. The partial index name already used the bare term
-- (`proj_decision_summary_rule_idx`), so it auto-tracks the renamed
-- column reference without a separate ALTER INDEX.
--
-- Forward-only per [[project_forward_only_migrations]].

ALTER TABLE proj_decision_summary
    RENAME COLUMN decision_rule TO rule;
