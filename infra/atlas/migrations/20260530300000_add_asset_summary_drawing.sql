-- Widen proj_equipment_asset_summary with the Asset.drawing facet:
-- engineering reference for the physical specimen, captured at
-- registration. Three nullable TEXT columns rather than a JSONB
-- blob so direct filtering ("all assets built to ICMS drawing
-- P4105") stays a simple WHERE.
--
-- Defaults to NULL for legacy rows that registered without a drawing
-- (additive-payload pattern at the aggregate layer mirrored here).
-- The projection's AssetRegistered branch backfills drawing_system /
-- drawing_number / drawing_revision when the event payload carries a
-- drawing object; absent payload key folds to all-NULL.
--
-- ## Why split into three columns
--
-- Same precedent as proj_recipe_method_signature unfolds Method's
-- composite fields into separate columns: keyset-paginated list
-- endpoints want one WHERE per facet without jsonb_extract_path. A
-- single Drawing VO with system+number+revision unfolds naturally.
--
-- ## CHECK constraint
--
-- drawing_system is constrained to the closed enum (ICMS / EDMS /
-- DOI) when present, NULL otherwise. Future enum additions require
-- a migration that drops + re-adds the CHECK with the wider set,
-- matching the lifecycle / condition CHECK pattern.
--
-- ## Forward-only
--
-- Pure ADD COLUMN; greenfield-friendly; no backfill needed (legacy
-- rows already lacked the drawing facet and stay NULL).

ALTER TABLE proj_equipment_asset_summary
    ADD COLUMN drawing_system   TEXT CHECK (
        drawing_system IS NULL
        OR drawing_system IN ('ICMS', 'EDMS', 'DOI')
    ),
    ADD COLUMN drawing_number   TEXT,
    ADD COLUMN drawing_revision TEXT;
