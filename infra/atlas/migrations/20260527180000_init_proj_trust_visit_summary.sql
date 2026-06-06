-- Phase visit-beta: initialise the proj_trust_visit_summary read model
-- backing list_visits / get_visit (slices land Phase epsilon API surface;
-- table exists from beta so Path C timestamps + downstream queries don't
-- need a follow-up migration).
--
-- Per [[project_visit_aggregate_design]]:
--   - Two-tier period split: planned_* live on STATE (operator-supplied
--     at registration); actual_* live HERE on the projection (derivable
--     from VisitArrived / VisitStarted / Visit{Completed, Cancelled,
--     Aborted, Voided} event occurred_at). Path C precedent.
--   - external_refs column shipped now (Phase beta) even though API
--     surface lands Phase epsilon; closes the migration-drift concern
--     surfaced in the gate review (P2-Design-3).
--   - parent_id column shipped now (Phase beta) even though
--     API surface lands Phase delta; same rationale.
--   - VisitType is a closed enum enforced by CHECK constraint; adding
--     a 6th value uses CORA's forward-only migration pattern (drop +
--     re-add the constraint).
--   - VisitStatus is a closed enum enforced by CHECK constraint;
--     mirrors the per-aggregate status-column pattern in
--     proj_agent_summary / proj_recipe_capability_summary.
--
-- Subscribed events:
--   - VisitRegistered  -> INSERT created_at + planned_*
--   - VisitArrived     -> UPDATE arrived_at + status='Arrived'
--   - VisitStarted     -> UPDATE started_at + status='InProgress'
--   - VisitHeld        -> UPDATE status='OnHold'
--   - VisitResumed     -> UPDATE status='InProgress'
--   - VisitCompleted   -> UPDATE completed_at + status='Completed'
--   - VisitCancelled   -> UPDATE completed_at + status='Cancelled'
--   - VisitAborted     -> UPDATE completed_at + status='Aborted'
--   - VisitVoided      -> UPDATE completed_at + status='Voided'
--
-- statushistory ships Phase zeta as a separate projection table
-- (proj_trust_visit_status_history); this projection does NOT carry
-- inline status history (FHIR R5 EncounterHistory precedent;
-- [[project_template_aggregate_timestamps]] Path C).
--
-- Phase gamma adds proj_trust_visit_presence in a separate migration.
-- Phase delta adds proj_trust_surface_active_visit in a separate
-- migration.

CREATE TABLE proj_trust_visit_summary (
    visit_id           UUID        PRIMARY KEY,
    policy_id          UUID        NOT NULL,
    surface_id         UUID        NOT NULL,
    type               TEXT        NOT NULL CHECK (
        type IN ('user', 'commissioning', 'maintenance', 'calibration', 'staff')
    ),
    status             TEXT        NOT NULL CHECK (
        status IN (
            'Planned', 'Arrived', 'InProgress', 'OnHold',
            'Completed', 'Cancelled', 'Aborted', 'Voided'
        )
    ),
    planned_start_at   TIMESTAMPTZ NOT NULL,
    planned_end_at     TIMESTAMPTZ NOT NULL,
    parent_id          UUID        NULL,
    external_refs      JSONB       NOT NULL DEFAULT '[]'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL,
    arrived_at         TIMESTAMPTZ,
    started_at         TIMESTAMPTZ,
    completed_at       TIMESTAMPTZ,
    last_status_reason TEXT,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- "All visits on this surface in this status" -- the dominant operator query.
CREATE INDEX proj_trust_visit_summary_surface_status_idx
    ON proj_trust_visit_summary (surface_id, status);

-- "Find visits scheduled in this window" -- BSS-subscriber + UI calendar query.
CREATE INDEX proj_trust_visit_summary_status_planned_idx
    ON proj_trust_visit_summary (status, planned_start_at);

-- Keyset for the eventual list_visits paginated read.
CREATE INDEX proj_trust_visit_summary_keyset_idx
    ON proj_trust_visit_summary (created_at, visit_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_trust_visit_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_trust_visit_summary')
ON CONFLICT DO NOTHING;
