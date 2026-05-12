-- Phase 8e-2a: Subject BC projection — subject summary for `GET /subjects`.
--
-- Folds the Subject BC's 7 lifecycle events (SubjectRegistered,
-- SubjectMounted, SubjectMeasured, SubjectRemoved, SubjectReturned,
-- SubjectStored, SubjectDiscarded) into a queryable read model.
-- Used by the `list_subjects` slice for `GET /subjects` keyset-
-- paginated list endpoint with optional status filter.
--
-- Status semantics: per `cora/subject/aggregates/subject/state.py`,
-- the Subject's status is derived from the event TYPE itself, not
-- from the payload (e.g., SubjectMounted always means status=Mounted).
-- The CHECK constraint here mirrors `SubjectStatus` enum values
-- (PascalCase per the BC-map status vocabulary). Adding a new event
-- type that produces a new status requires updating this CHECK in
-- a forward migration.
--
-- Mutable read model (rebuildable from events). cora_app gets full
-- DML; the arch-fitness test `test_projection_grants` enforces the
-- GRANT exists. Projection name `proj_subject_summary` matches:
--   - the table name (here)
--   - the bookmark row (INSERT below)
--   - `SubjectSummaryProjection.name`
-- (cora.subject.projections.subject_summary). The arch-fitness test
-- `test_projection_table_match` enforces alignment.

CREATE TABLE proj_subject_summary (
    subject_id  UUID        PRIMARY KEY,
    name        TEXT        NOT NULL,
    status      TEXT        NOT NULL CHECK (
        status IN (
            'Received', 'Mounted', 'Measured', 'Removed',
            'Returned', 'Stored', 'Discarded'
        )
    ),
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_subject_summary_keyset_idx
    ON proj_subject_summary (created_at, subject_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_subject_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_subject_summary')
ON CONFLICT DO NOTHING;
