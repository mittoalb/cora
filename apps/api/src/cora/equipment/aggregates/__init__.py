"""Aggregates owned by the Equipment BC.

Phase 5a shipped `Family` (technique-class catalog). Phase 5b
adds `Asset` (physical equipment instance, hierarchical via
parent_id, lifecycle-managed). The two coexist in this BC because
Recipe.Method references `Family` and Recipe.Plan references
`Asset`, and both are Foundation-tier shared concepts (per the
BC map).
"""
