-- Phase 6k.cleanup: drop UNIQUE INDEX on `proj_recipe_capability_summary (code)`.
--
-- The original 6k migration (20260518200000) created this UNIQUE
-- INDEX to enforce code uniqueness at the projection layer. The
-- gate review flagged that the aggregate decider does NOT enforce
-- code uniqueness (define_capability only checks stream non-existence),
-- so a second define_capability with the same code but a fresh id
-- would: (a) successfully append events to a new stream, then
-- (b) blow up the projection INSERT with `UniqueViolation`,
-- poisoning the bookmark + diverging aggregate state from projection.
--
-- Resolution: drop the projection-side uniqueness constraint, match
-- CORA's eventual-consistency convention (Family.name, Method.name,
-- Plan.name, Practice.name all lack uniqueness checks). Code-
-- uniqueness becomes operator-curation discipline at v1, enforced
-- catalog-side rather than at the aggregate / projection layer. Add
-- decider-level uniqueness via a list-by-code projection if/when a
-- real collision happens in pilot.
--
-- This is the cleanup follow-up to the original 6k migration, NOT
-- a forward-incompatible change to it (the table + columns + bookmark
-- stay). Standard forward-only DROP INDEX; allowed-data-preserving.

-- atlas:safety:allow=drop-index-allowed-data-preserving

DROP INDEX IF EXISTS proj_recipe_capability_summary_code_idx;
