-- Adds proj_calibration_summary.latest_revision_content_hash for
-- Candidate A (content-addressed identity) CalibrationRevision adoption.
--
-- Per project_content_addressed_identity_design, CalibrationRevisionAppended
-- now carries a SHA-256 over the revision's content subset (value +
-- status + source_kind + source_id + decided_by_decision_id +
-- supersedes_revision_id), captured in the event payload by the
-- decider per the non-determinism principle. The summary projection
-- holds the latest revision's hash (rather than every revision) so
-- equivalence lookups against current values stay an indexed scan;
-- per-revision history hashes are recoverable via fold + the event
-- payload until proj_calibration_revisions lands.
--
-- Mirrors the Method (20260524130000) + Plan (20260525130000)
-- adoptions: NULL-able + additive; pre-rollout CalibrationRevisionAppended
-- events have no content_hash on the payload and project NULL into
-- this column (matches CalibrationRevision.content_hash: str | None
-- additive-state pattern). No backfill per project_forward_only_migrations.
--
-- Partial index on non-NULL keeps pre-rollout rows out of the b-tree
-- and covers the `WHERE latest_revision_content_hash = $1` equivalence
-- shape (cherry-pick analogue, "find calibrations whose latest value
-- equals this hash" reproducibility queries).

ALTER TABLE proj_calibration_summary
    ADD COLUMN latest_revision_content_hash TEXT;

CREATE INDEX ix_proj_calibration_summary_latest_revision_content_hash
    ON proj_calibration_summary (latest_revision_content_hash)
    WHERE latest_revision_content_hash IS NOT NULL;
