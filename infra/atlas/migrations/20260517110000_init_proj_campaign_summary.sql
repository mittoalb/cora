-- Phase 6i-b: Campaign BC's first projection -- campaign summary read model.
--
-- Folds the Campaign aggregate's lifecycle events into the
-- `proj_campaign_summary` read model used by the
-- `list_campaigns` slice for `GET /campaigns` keyset-paginated list
-- endpoint with optional status / intent / lead_actor_id /
-- subject_id / tag filters.
--
-- Table name `proj_campaign_summary` follows the cross-BC
-- per-aggregate projection convention `proj_<bc>_<aggregate>_summary`
-- (Caution: proj_caution_summary, Supply: proj_supply_summary).
-- Campaign is a NEW BC sibling-to-Recipe per the BC map and the
-- design memo, NOT a fifth aggregate inside Recipe; the projection
-- name reflects the owning BC.
--
-- Subscribed events:
--   - CampaignRegistered -> INSERT (status='Planned', started_at=NULL,
--                                   last_status_*=NULL, run_count=0)
--   - CampaignStarted    -> UPDATE status='Active' + started_at
--                                  + last_status_changed_at
--   - CampaignHeld       -> UPDATE status='Held' + last_status_reason
--                                  + last_status_changed_at
--   - CampaignResumed    -> UPDATE status='Active'
--                                  + last_status_changed_at
--                                  (last_status_reason preserved)
--   - CampaignClosed     -> UPDATE status='Closed'
--                                  + last_status_changed_at
--   - CampaignAbandoned  -> UPDATE status='Abandoned'
--                                  + last_status_reason
--                                  + last_status_changed_at
--
-- ## Identity + denorm
--
-- `campaign_id` is the stable opaque CORA UUID (PK). `run_count` is
-- the denorm size of `Campaign.run_ids`; the full set lives on the
-- aggregate stream (queried via `get_campaign` when needed). Day-1
-- (6i-b) `run_count` stays at 0 because membership-mutation events
-- (CampaignRunAdded / Removed) land in 6i-c with the Run aggregate
-- evolution.
--
-- ## Audit columns
--
-- `started_at` is set on the FIRST transition out of Planned
-- (CampaignStarted; Planned -> Active only). CampaignResumed (Held ->
-- Active) does NOT clobber `started_at` -- the first-start
-- timestamp is preserved as audit truth for "when did this campaign
-- begin work".
--
-- `last_status_changed_at` is nullable until the campaign transitions
-- out of Planned for the first time; tracks every subsequent
-- transition.
--
-- `last_status_reason` is populated by Held + Abandoned events
-- (operator-required reason). CampaignResumed preserves the value
-- per design memo ("keep it -- audit value"): "why was it held
-- before the resume" stays readable. CampaignStarted / Closed do
-- not set it.
--
-- ## Pagination + hot-path indexes
--
-- Keyset pagination on `(registered_at, campaign_id)`. `registered_at`
-- is set once at CampaignRegistered (immutable), so it's a stable
-- keyset key.
--
-- Per-filter scalar indexes on lead_actor_id and subject_id support
-- the operator-dashboard filters ("campaigns I lead", "campaigns for
-- this subject").
--
-- Tags GIN supports the `WHERE $N = ANY(tags)` filter pattern (same
-- shape as the caution projection).
--
-- Partial status index supports the default "open campaigns" filter
-- (Planned + Active + Held); the closed terminals are excluded from
-- the default list view per design memo.
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_campaign_summary (
    campaign_id              UUID        PRIMARY KEY,
    name                     TEXT        NOT NULL,
    intent                   TEXT        NOT NULL CHECK (
        intent IN ('Series', 'Sweep', 'Coordinated', 'Block')
    ),
    status                   TEXT        NOT NULL CHECK (
        status IN ('Planned', 'Active', 'Held', 'Closed', 'Abandoned')
    ),
    lead_actor_id            UUID        NOT NULL,
    subject_id               UUID,
    description              TEXT,
    tags                     TEXT[]      NOT NULL DEFAULT '{}',
    external_id              TEXT,
    run_count                INTEGER     NOT NULL DEFAULT 0,
    registered_at            TIMESTAMPTZ NOT NULL,
    started_at               TIMESTAMPTZ,
    last_status_changed_at   TIMESTAMPTZ,
    last_status_reason       TEXT,
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Keyset pagination on `(registered_at, campaign_id)`.
CREATE INDEX proj_campaign_summary_keyset_idx
    ON proj_campaign_summary (registered_at, campaign_id);

-- "Campaigns I lead" filter (PI / lead-operator dashboard).
CREATE INDEX proj_campaign_summary_lead_actor_idx
    ON proj_campaign_summary (lead_actor_id);

-- "Campaigns for this subject" filter (loose subject ref; LOOSE
-- policy per design memo, but the read-side filter is useful even
-- when not aggregate-enforced).
CREATE INDEX proj_campaign_summary_subject_idx
    ON proj_campaign_summary (subject_id);

-- GIN index for `$N = ANY(tags)` filter on list_campaigns.
CREATE INDEX proj_campaign_summary_tags_gin_idx
    ON proj_campaign_summary USING GIN (tags);

-- Partial index for the default "open campaigns" filter
-- (status IN {Planned, Active, Held}). Closed + Abandoned are
-- excluded from the default list view per design memo.
CREATE INDEX proj_campaign_summary_open_idx
    ON proj_campaign_summary (status)
    WHERE status IN ('Planned', 'Active', 'Held');

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_campaign_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_campaign_summary')
ON CONFLICT DO NOTHING;
