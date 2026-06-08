"""Vertical slice for the `RemoveFacilityTrustAnchorCredential` command.

Removes a credential id from a Facility's `trust_anchor_credential_ids`
frozenset. Strict-not-idempotent: re-removing raises. Sibling of
`add_facility_trust_anchor_credential`; both ship together per the
Asset.alternate_identifiers add+remove bundled precedent.

Mirror of `cora.equipment.features.remove_asset_alternate_identifier`
in shape (command + decider + handler + route + tool + __init__).
"""

from cora.federation.features.remove_facility_trust_anchor_credential import tool
from cora.federation.features.remove_facility_trust_anchor_credential.command import (
    RemoveFacilityTrustAnchorCredential,
)
from cora.federation.features.remove_facility_trust_anchor_credential.decider import decide
from cora.federation.features.remove_facility_trust_anchor_credential.handler import (
    Handler,
    bind,
)
from cora.federation.features.remove_facility_trust_anchor_credential.route import router

__all__ = [
    "Handler",
    "RemoveFacilityTrustAnchorCredential",
    "bind",
    "decide",
    "router",
    "tool",
]
