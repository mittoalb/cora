"""The `AddFacilityTrustAnchorCredential` command: intent dataclass for this slice.

`facility_id` is the target Facility aggregate. `credential_id` is the
Credential id to add to the Facility's `trust_anchor_credential_ids`
frozenset. The decider rejects:
  - a non-existent Facility (FacilityNotFoundError, 404)
  - a Facility with kind=Area OR status=Decommissioned (shared
    lifecycle/kind guard via FacilityCannotAddTrustAnchorCredentialError, 409)
  - a credential_id already in the set (strict-not-idempotent via
    FacilityTrustAnchorCredentialAlreadyPresentError, 409)

The principal-id of the invoker is supplied separately by the
application handler at call time and stamped onto the
`FacilityTrustAnchorCredentialAdded` event as `added_by`.

This slice does NOT validate that the credential id resolves to an
existing Credential row; that check is structurally distinct and would
require widening the FacilityLookup port or introducing a per-handler
CredentialLookup dependency. Today operators are trusted to add valid
credential ids; Sub-Slice C's Seal decider rewrite enforces the
membership invariant at use-time, which surfaces typos as
SealCredentialNotTrustAnchorError if the trust-anchor id ever differs
from a real credential id.
"""

from dataclasses import dataclass

from cora.federation.aggregates._value_types import CredentialId, FacilityId


@dataclass(frozen=True, slots=True)
class AddFacilityTrustAnchorCredential:
    """Add a Credential id to a Facility's trust-anchor set (strict-not-idempotent)."""

    facility_id: FacilityId
    credential_id: CredentialId
