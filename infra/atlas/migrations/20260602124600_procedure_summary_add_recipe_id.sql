-- Procedure summary projection: additive recipe_id column.
--
-- Pre-Recipe-rewrite Procedures (registered via the legacy
-- `register_procedure` slice, NOT `register_procedure_from_recipe`)
-- carry `recipe_id=NULL` in state and now also in the projection.
-- Read paths filtering `WHERE recipe_id IS NOT NULL` correctly
-- exclude ceremony Procedures; the `recipe_id` column is NOT total
-- over Procedures. Do not assume otherwise in audit-query authoring.
--
-- Additive evolution: existing rows keep recipe_id=NULL until
-- explicit backfill (deferred; ceremony Procedures legitimately have
-- no Recipe binding).
--
-- Mutable read model. cora_app keeps its existing DML grants on
-- proj_operation_procedure_summary.

ALTER TABLE proj_operation_procedure_summary
    ADD COLUMN recipe_id UUID;

CREATE INDEX proj_operation_procedure_summary_recipe_id_idx
    ON proj_operation_procedure_summary (recipe_id)
    WHERE recipe_id IS NOT NULL;
