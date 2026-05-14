"""Vertical slices owned by the Recipe BC.

Slices ship per aggregate / per state transition:
  - 6a: define_method, get_method
  - 6b: version_method, deprecate_method
  - 6d: define_practice, get_practice, version_practice, deprecate_practice
  - 6e: define_plan, get_plan, version_plan, deprecate_plan
  - 6c (deferred): Method/Practice/Plan enrichment (description,
    owner) — defer-candidate
  - 6f: Run aggregate slices (the keystone)
  - 6g-a: update_method_parameters_schema (Method.parameters_schema
    JSON Schema declaration; pre-positions Plan defaults / Run
    overrides in 6g-b/c)
  - 6g-b: update_plan_parameter_defaults (Plan.parameter_defaults
    PATCH RFC 7396 with merge_patch reuse; validated against owning
    Method.parameters_schema with permissive-when-None posture)
  - 6g-c (future): Run.parameter_overrides + effective_parameters
    snapshot on RunStarted
"""
