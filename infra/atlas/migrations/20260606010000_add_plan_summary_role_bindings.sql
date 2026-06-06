-- Widen proj_recipe_plan_summary with the Plan.role_bindings facet:
-- the (role_name, asset_id) pairs that fill each of the bound
-- Method's required_roles (IEC 81346 Function aspect; slice 2 of
-- the positional role-tagging workstream). Stored as a sorted
-- JSONB array of `{"role_name", "asset_id"}` objects, sorted by
-- `role_name` ASC at write time for byte-stable replay.
--
-- Additive JSONB array per [[project-plan-role-bindings-design]].
-- Legacy PlanDefined-only streams fold to an empty array via the
-- NOT NULL DEFAULT '[]'::jsonb shape; the slice-2 PlanRoleBound /
-- PlanRoleUnbound projection branches read-modify-write the array
-- via pure SQL jsonb_agg + DISTINCT ON / WHERE filter (mirrors the
-- slice-1 method projection writers).
--
-- ## No GIN index
--
-- Defer the GIN index until a query in any view builder or analytics
-- path filters by role_name or asset_id. The slice 2 consumption
-- pattern reads role_bindings alongside the rest of the Plan row;
-- no current call site needs containment lookup. The cost of an
-- unused GIN index is per-row write amplification.
--
-- ## Forward-only
--
-- Pure ADD COLUMN with safe default; greenfield-friendly; no
-- backfill needed. Rollback via a NEW compensating migration per
-- [[project-forward-only-migrations]].

ALTER TABLE proj_recipe_plan_summary
    ADD COLUMN role_bindings JSONB NOT NULL DEFAULT '[]'::jsonb;
