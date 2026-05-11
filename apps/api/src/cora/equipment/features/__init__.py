"""Vertical slices owned by the Equipment BC.

Slices ship per aggregate / per state transition:
  - 5a: define_capability, get_capability
  - 5b: register_asset
  - 5c: activate_asset, decommission_asset
  - 5d: relocate_asset (hierarchy mutation)
  - 5e: get_asset, enter_maintenance, restore_from_maintenance
  - 5f+: Capability transitions (version, deprecate);
    Asset additive facets (condition, settings, ports, owner, PIDINST)
"""
