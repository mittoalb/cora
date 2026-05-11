"""Vertical slices owned by the Recipe BC.

Slices ship per aggregate / per state transition:
  - 6a: define_method, get_method
  - 6b: version_method, deprecate_method
  - 6d: define_practice, get_practice, version_practice, deprecate_practice
  - 6e: define_plan, get_plan, version_plan, deprecate_plan
  - 6c (deferred): Method/Practice/Plan enrichment (description,
    owner, default parameters) — defer-candidate
  - 6f: Run aggregate slices (the keystone)
"""
