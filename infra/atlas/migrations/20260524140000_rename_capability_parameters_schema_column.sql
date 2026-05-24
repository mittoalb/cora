-- Cluster 5 of the 2026-05-22 cross-package consistency audit: rename
-- the Recipe.Capability projection column `parameter_schema_present`
-- to `parameters_schema_present`. The bare field name was the lone
-- outlier in the Capability aggregate; Method.parameters_schema (and
-- the existing `update_method_parameters_schema` slice name) already
-- use the plural form. Per the locked R3 family-noun primacy rule
-- (case study: `parameter_defaults` -> `default_parameters`), the
-- thing-being-schema'd is a collection -> family noun pluralises.
--
-- Source tree renames the field on the aggregate / event-payload /
-- decider / route / tool / projection / docs layers in lockstep;
-- this migration brings the projection column along.
--
-- Forward-only per [[project_forward_only_migrations]].

ALTER TABLE proj_recipe_capability_summary
    RENAME COLUMN parameter_schema_present TO parameters_schema_present;
