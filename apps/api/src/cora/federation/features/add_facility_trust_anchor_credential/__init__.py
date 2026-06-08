"""Vertical slice for the `AddFacilityTrustAnchorCredential` command.

Adds a credential id to a Facility's `trust_anchor_credential_ids`
frozenset. Strict-not-idempotent: re-adding raises. Per
[[project-slice6-design]] Sub-Slice B; together with the sibling
remove slice this enables Sub-Slice C to delete the SealCrossFacilityBindingError
string-equality defense and replace it with set-membership against
this column.

Mirror of `cora.equipment.features.add_asset_alternate_identifier`
in shape (command + decider + handler + route + tool + __init__).
"""

from cora.federation.features.add_facility_trust_anchor_credential import tool
from cora.federation.features.add_facility_trust_anchor_credential.command import (
    AddFacilityTrustAnchorCredential,
)
from cora.federation.features.add_facility_trust_anchor_credential.decider import decide
from cora.federation.features.add_facility_trust_anchor_credential.handler import (
    Handler,
    bind,
)
from cora.federation.features.add_facility_trust_anchor_credential.route import router

__all__ = [
    "AddFacilityTrustAnchorCredential",
    "Handler",
    "bind",
    "decide",
    "router",
    "tool",
]
