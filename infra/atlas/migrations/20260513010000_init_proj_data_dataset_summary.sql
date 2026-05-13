-- Phase 8e-6: Data BC's first projection — dataset summary.
--
-- Folds the Dataset aggregate's 2 lifecycle events into the
-- `proj_data_dataset_summary` read model used by the `list_datasets`
-- slice for `GET /datasets` keyset-paginated list endpoint.
--
-- Subscribed events:
--   - DatasetRegistered  -> INSERT (status=Registered, name + uri +
--                                   producing_run_id? + subject_id?
--                                   from genesis payload)
--   - DatasetDiscarded   -> UPDATE status=Discarded   (terminal)
--
-- Genesis-event refs (producing_run_id, subject_id) come from the
-- payload only and never change. Both nullable per Data BC's
-- "Datasets can exist without a producing Run or measured Subject"
-- stance (Phase 7 register_dataset cross-track validation).
--
-- The rich payload fields (checksum, byte_size, media_type,
-- conforms_to, derived_from) are intentionally NOT in this
-- projection; they're either single-record-detail (use GET
-- /datasets/<id>) or list-typed (future join projection
-- proj_data_dataset_lineage when use cases demand "all datasets
-- derived from X").
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_data_dataset_summary (
    dataset_id        UUID        PRIMARY KEY,
    name              TEXT        NOT NULL,
    uri               TEXT        NOT NULL,
    producing_run_id  UUID,
    subject_id        UUID,
    status            TEXT        NOT NULL CHECK (
        status IN ('Registered', 'Discarded')
    ),
    created_at        TIMESTAMPTZ NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_data_dataset_summary_keyset_idx
    ON proj_data_dataset_summary (created_at, dataset_id);

CREATE INDEX proj_data_dataset_summary_run_idx
    ON proj_data_dataset_summary (producing_run_id)
    WHERE producing_run_id IS NOT NULL;

CREATE INDEX proj_data_dataset_summary_subject_idx
    ON proj_data_dataset_summary (subject_id)
    WHERE subject_id IS NOT NULL;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_data_dataset_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_data_dataset_summary')
ON CONFLICT DO NOTHING;
