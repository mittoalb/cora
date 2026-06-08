"""Vertical slice for the `RegisterFacility` command.

Module-as-namespace surface, symmetric with `register_credential`:

    from cora.federation.features import register_facility

    cmd = register_facility.RegisterFacility(
        code="aps",
        display_name="Advanced Photon Source",
        kind=FacilityKind.SITE,
        parent_id=None,
    )
    handler = register_facility.bind(deps)
    facility_id = await handler(cmd, principal_id=..., correlation_id=...)

Unlike `register_credential`, this slice writes ONLY the Facility stream
(no cross-BC Decision audit) per [[project_facility_aggregate_design]]
Lock "No cross-BC atomic-writes in slice 5".
"""

from cora.federation.features.register_facility import tool
from cora.federation.features.register_facility.command import RegisterFacility
from cora.federation.features.register_facility.decider import decide
from cora.federation.features.register_facility.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.federation.features.register_facility.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "RegisterFacility",
    "bind",
    "decide",
    "router",
    "tool",
]
