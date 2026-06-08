"""The `RemoveFacilityTrustAnchorCredential` command: intent dataclass for this slice.

`facility_id` is the target Facility aggregate. `credential_id` is the
Credential id to remove from the Facility's `trust_anchor_credential_ids`
frozenset. `reason` is operator-supplied free text captured at the API
boundary for audit-log breadcrumb purposes ("key compromise", "rotation
cleanup", "decommissioned credential garbage-collect"); flows through
to the `FacilityTrustAnchorCredentialRemoved` event payload.

The decider rejects:
  - a non-existent Facility (FacilityNotFoundError, 404)
  - a Facility with status=Decommissioned (shared lifecycle/kind guard
    via FacilityCannotAddTrustAnchorCredentialError, 409; note the
    "Add" verb in the shared class name carries the Asset-precedent
    convention of one shared error for both directions)
  - a credential_id not in the set (strict-not-idempotent via
    FacilityTrustAnchorCredentialNotPresentError, 409)

Note: kind=Area Facilities can NEVER have non-empty trust anchors
(enforced by the Facility __post_init__ invariant + the add decider's
guard); the remove decider therefore does not need a separate kind=Area
guard. If an Area Facility somehow had a non-empty set (which is
structurally impossible), the credential_id-not-in-set guard would
fire before the lifecycle check.
"""

from dataclasses import dataclass

from cora.federation.aggregates._value_types import CredentialId, FacilityId


@dataclass(frozen=True, slots=True)
class RemoveFacilityTrustAnchorCredential:
    """Remove a Credential id from a Facility's trust-anchor set (strict-not-idempotent)."""

    facility_id: FacilityId
    credential_id: CredentialId
    reason: str | None = None
