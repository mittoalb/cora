"""Vertical slices owned by the Recipe BC.

Slices ship per aggregate / per state transition:
  - define_method, get_method, version_method, deprecate_method
  - define_practice, get_practice, version_practice, deprecate_practice
  - define_plan, get_plan, version_plan, deprecate_plan
  - Method/Practice/Plan enrichment (description, owner) is a defer
    candidate
  - Run aggregate slices (the keystone)
  - update_method_parameters_schema (Method.parameters_schema JSON
    Schema declaration; pre-positions Plan defaults / Run overrides)
  - update_plan_default_parameters (Plan.default_parameters PATCH
    RFC 7396 with merge_patch reuse; validated against owning
    Method.parameters_schema; STRICT when Method has no schema,
    mirroring Asset.settings's "no Capabilities → reject" anchor)
  - Run.override_parameters + effective_parameters snapshot on
    RunStarted (same strict-when-no-schema posture)
  - add_plan_wire / remove_plan_wire (Plan.wires graph of typed
    port-to-port connections between bound Assets; per-edge
    add/remove slices mirroring Asset.ports's add/remove_asset_port;
    strict direction + signal_type + port-existence validation
    against Asset.ports; fan-in forbidden, fan-out allowed; see
    [[project_plan_wiring_design]])
  - define_capability, version_capability, deprecate_capability,
    get_capability: universal operations-layer template aggregate
    sitting above heterogeneous executor shapes (Method-chain for
    science, Procedure for ceremony); ExecutorShape closed v1 enum
    {Method, Procedure} ships here too (folded per
    [[project_capability_aggregate_design]]). Method.capability_id
    FK + Plan.activate cross-BC affordance-cover validation follow;
    Procedure.capability_id additive evolution lands with Operation.
"""
