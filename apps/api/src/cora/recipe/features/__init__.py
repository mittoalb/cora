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
  - 6g-b: update_plan_default_parameters (Plan.default_parameters
    PATCH RFC 7396 with merge_patch reuse; validated against owning
    Method.parameters_schema; STRICT when Method has no schema, post-6g
    audit reversal mirroring 5g-c's "no Capabilities → reject" anchor)
  - 6g-c: Run.override_parameters + effective_parameters snapshot
    on RunStarted (same strict-when-no-schema posture)
  - 6h: add_plan_wire / remove_plan_wire (Plan.wires graph of
    typed port-to-port connections between bound Assets; per-edge
    add/remove slices mirroring 5h's add/remove_asset_port; strict
    direction + signal_type + port-existence validation against
    Asset.ports; fan-in forbidden, fan-out allowed; see
    [[project_plan_wiring_design]])
"""
