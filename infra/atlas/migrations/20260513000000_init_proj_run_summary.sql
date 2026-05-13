-- Phase 8e-5: Run BC's first projection — run summary.
--
-- Folds the Run aggregate's 7 lifecycle events into the
-- `proj_run_summary` read model used by the `list_runs` slice for
-- `GET /runs` keyset-paginated list endpoint with optional status
-- and plan_id filters.
--
-- Subscribed events:
--   - RunStarted     -> INSERT (status=Running, name, plan_id, subject_id, raid)
--   - RunHeld        -> UPDATE status=Held
--   - RunResumed     -> UPDATE status=Running
--   - RunCompleted   -> UPDATE status=Completed   (terminal)
--   - RunAborted     -> UPDATE status=Aborted     (terminal)
--   - RunStopped     -> UPDATE status=Stopped     (terminal)
--   - RunTruncated   -> UPDATE status=Truncated   (terminal)
--
-- Cross-aggregate refs (plan_id, subject_id, raid) come from the
-- genesis event payload only and never change. The lifecycle UPDATEs
-- only touch `status`. plan_id surfaces the cross-aggregate filter
-- ("show me all Runs for Plan X").
--
-- subject_id is nullable (Plan-only Runs without a Subject mount
-- per the Run BC's "optional Subject binding" stance from 6f-1).
-- raid is nullable (ISO-23527 RAiD; populated forward-compat per
-- Phase 7 retrofit; older RunStarted events without raid still fold
-- cleanly).
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_run_summary (
    run_id         UUID        PRIMARY KEY,
    name           TEXT        NOT NULL,
    plan_id        UUID        NOT NULL,
    subject_id     UUID,
    raid           TEXT,
    status         TEXT        NOT NULL CHECK (
        status IN ('Running', 'Held', 'Completed', 'Aborted', 'Stopped', 'Truncated')
    ),
    created_at     TIMESTAMPTZ NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_run_summary_keyset_idx
    ON proj_run_summary (created_at, run_id);

CREATE INDEX proj_run_summary_plan_idx
    ON proj_run_summary (plan_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_run_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_run_summary')
ON CONFLICT DO NOTHING;
