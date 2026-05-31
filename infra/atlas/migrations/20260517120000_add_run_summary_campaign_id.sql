-- Phase 6i-c follow-up (Campaign Watch #10): add campaign_id to the
-- Run summary projection so `list_runs?campaign_id=<uuid>` can serve
-- "show me all Runs in Campaign X" without folding individual Run
-- streams or 2-hop-joining through proj_campaign_summary.run_ids.
--
-- ## Why a column, not the dict itself
--
-- Mirrors how 11a-c-3 chose denormalized columns on
-- `proj_safety_clearance_summary` for the binding UUID arrays. The
-- campaign_id is a single nullable UUID (one-Campaign-per-Run lock
-- locked in `[[project_campaign_design]]`); plain UUID column with a
-- partial index is the right shape.
--
-- ## Why nullable + partial index
--
-- Most Runs are standalone (no Campaign membership). Indexing only
-- the rows where the column is non-null keeps the index small while
-- still serving the "list Runs in Campaign X" query path efficiently.
-- Mirrors the partial-index choice on `proj_caution_summary` for the
-- "Active only" hot path.
--
-- ## Forward-compat semantics
--
-- Existing rows backfill cleanly as NULL (the column nullable, no
-- DEFAULT needed). Pre-6i-c RunStarted payloads lack the campaign_id
-- key entirely; the projection reads via `.get("campaign_id")` which
-- returns None on the legacy shape, mapping to SQL NULL.
--
-- Subscribes to two additional event types post-migration:
--   - RunAddedToCampaign   -> UPDATE campaign_id = $2 (post-hoc add)
--   - RunRemovedFromCampaign -> UPDATE campaign_id = NULL (remove)
-- RunStarted already covered (at-start campaign_id via payload).
--
-- Pure ADD COLUMN with safe NULL backfill; greenfield-friendly.

ALTER TABLE proj_run_summary
    ADD COLUMN campaign_id UUID;

CREATE INDEX proj_run_summary_campaign_idx
    ON proj_run_summary (campaign_id)
    WHERE campaign_id IS NOT NULL;
