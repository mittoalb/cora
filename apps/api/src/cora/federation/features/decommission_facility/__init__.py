"""Vertical slice for the `DecommissionFacility` command.

Module-as-namespace surface, symmetric with `register_facility`:

    from cora.federation.features import decommission_facility

    cmd = decommission_facility.DecommissionFacility(
        facility_id=facility_id,
        reason="end-of-life",
    )
    handler = decommission_facility.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

Terminal transition (Active -> Decommissioned); strict-not-idempotent
per the revoke_credential precedent. Single-stream write per
[[project_facility_aggregate_design]] Lock "No cross-BC atomic-writes
in slice 5".
"""

from cora.federation.features.decommission_facility import tool
from cora.federation.features.decommission_facility.command import DecommissionFacility
from cora.federation.features.decommission_facility.decider import decide
from cora.federation.features.decommission_facility.handler import Handler, bind
from cora.federation.features.decommission_facility.route import router

__all__ = [
    "DecommissionFacility",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
