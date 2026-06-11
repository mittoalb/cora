-- Equipment BC: add affordances column to Family summary projection
-- (Layer 3 sub-slice 3B follow-up; column the 3B work assumed but
-- never created).
--
-- ## Why
--
-- 3B shipped the FamilyLookup port + projection writer
-- (cora/equipment/projections/family.py) that read and write
-- proj_equipment_family_summary.affordances, and the 3B
-- add_proj_equipment_family_summary_presents_as migration ASSUMED an
-- affordances column already existed ("Mirrors the required_affordances
-- TEXT[] column already present on the table"). It did not: the table
-- descends from proj_equipment_capability_summary (init
-- 20260512290000), which carried only capability_id / name / status /
-- version_tag / created_at / updated_at, and the capability->family
-- rename (20260518100000) added no affordances column. settings_schema_present
-- + lifecycle timestamps + presents_as are the only later additions.
--
-- The PostgresFamilyLookup SELECT and the family.py writer therefore
-- referenced a column that was never created. In-memory tests
-- (InMemoryFamilyLookup) do not hit Postgres, so the gap surfaced only
-- on the integration tier as
-- `UndefinedColumnError: column "affordances" of relation
-- "proj_equipment_family_summary" does not exist`.
--
-- ## What this migration does
--
-- Adds `affordances TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[]` so existing
-- rows default to the empty set. The 3B projection writer populates it
-- from FamilyDefined / FamilyVersioned event payloads (wholesale-replace
-- on version per the 5j Family.affordances semantics); a projection
-- replay-from-zero repopulates pre-existing Family rows from their
-- FamilyDefined payloads.
--
-- Mutable read model; cora_app already has full DML, no GRANT change.

ALTER TABLE proj_equipment_family_summary
    ADD COLUMN affordances TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];

COMMENT ON COLUMN proj_equipment_family_summary.affordances IS
    'Family Affordance value strings backing the Layer 3 sub-slice 3B FamilyLookup affordance-superset check. Wholesale-replaced on FamilyVersioned per 5j semantics.';
