"""Aggregates owned by the Equipment BC.

Two aggregates: `Family` (technique-class catalog) and `Asset`
(physical equipment instance, hierarchical via parent_id,
lifecycle-managed). The two coexist in this BC because Recipe.Method
references `Family` and Recipe.Plan references `Asset`, and both are
Foundation-tier shared concepts per the BC map.
"""
