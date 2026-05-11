"""Vertical slices owned by the Recipe BC.

Slices ship per aggregate / per state transition:
  - 6a: define_method, get_method
  - 6b: version_method, deprecate_method
  - 6c: Method enrichment (description, owner) — defer-candidate
  - 6d: define_practice, get_practice (+ practice transitions)
  - 6e: define_plan, bind_plan, get_plan (+ plan lifecycle)
  - 6f: Run aggregate slices
"""
