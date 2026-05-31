"""Pure decider for the `RotateSealOnlineKey` command.

Live -> Live transition that swaps `online_key_ref` to a fresh
Credential. Strict-not-idempotent: re-rotating to the same ref the
slot already holds raises `SealCannotRotateError` so the audit
gesture stays meaningful (the offline-root authorises a real change
each time).

`rotated_by_actor_id` is handler-injected from the request envelope's
`principal_id` (capture-don't-recompute) and stamped onto the emitted
`SealOnlineKeyRotated` event for the audit denorm.

`new_online_credential` is handler-injected too: the handler resolves
the new ref via the `CredentialLookup` port BEFORE invoking the
decider, and the decider partitions on the `purpose` / `status` of the
projection row. Mirrors the start_run pattern (handler loads upstream
projections, threads them into the pure decider). The decider stays
pure: no I/O, no await.

The key-separation invariant (sec-4 AH#15) is enforced by building the
prospective post-transition `Seal` state with the new online ref and
calling `verify_key_separation` before returning events. The helper
raises `SealKeyCollisionError` when `new_online_key_ref` would equal
`offline_key_ref`; HTTP routes this to 422.

## Validation

  - State must not be None (Seal must exist) -> SealNotFoundError
  - Current status must be Live -> SealCannotRotateError
  - new_online_key_ref must differ from current online_key_ref
    -> SealCannotRotateError (no-op rotation rejected)
  - new_online_credential must not be None (the projection must know
    the ref) -> CredentialNotFoundError (per the start_run ->
    PlanNotFoundError / MethodNotFoundError precedent)
  - new_online_credential.purpose must equal "SealOnlineSigning"
    -> SealKeyPurposeMismatchError (HTTP 422)
  - new_online_credential.facility_id must equal state.facility_id
    -> SealCrossFacilityBindingError (HTTP 409; cross-tenant key
    mounting defense)
  - new_online_credential.status must equal "Active"
    -> SealCannotRotateWithInactiveCredentialError (HTTP 409;
    Rotating or Revoked secrets cannot back a Seal)
  - new_online_key_ref must differ from offline_key_ref
    -> SealKeyCollisionError (via verify_key_separation helper)
"""

from dataclasses import replace
from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.credential import (
    CredentialNotFoundError,
    CredentialPurpose,
    CredentialStatus,
)
from cora.federation.aggregates.seal import (
    Seal,
    SealCannotRotateError,
    SealCannotRotateWithInactiveCredentialError,
    SealCrossFacilityBindingError,
    SealKeyPurposeMismatchError,
    SealNotFoundError,
    SealOnlineKeyRotated,
    SealStatus,
    verify_key_separation,
)
from cora.federation.features.rotate_seal_online_key.command import (
    RotateSealOnlineKey,
)
from cora.infrastructure.ports.credential_lookup import CredentialLookupResult

_ONLINE_SLOT = "online_key_ref"


def decide(
    state: Seal | None,
    command: RotateSealOnlineKey,
    *,
    now: datetime,
    rotated_by_actor_id: UUID,
    new_online_credential: CredentialLookupResult | None,
) -> list[SealOnlineKeyRotated]:
    """Decide the events produced by rotating the Seal online key.

    Invariants:
      - State must not be None -> SealNotFoundError
      - state.status must be Live -> SealCannotRotateError
      - new_online_key_ref must differ from state.online_key_ref
        -> SealCannotRotateError (no-op rotation rejected)
      - new_online_credential must not be None
        -> CredentialNotFoundError (unknown credential ref)
      - new_online_credential.purpose must be SealOnlineSigning
        -> SealKeyPurposeMismatchError
      - new_online_credential.facility_id must equal state.facility_id
        -> SealCrossFacilityBindingError
      - new_online_credential.status must be Active
        -> SealCannotRotateWithInactiveCredentialError
      - new_online_key_ref must differ from state.offline_key_ref
        -> SealKeyCollisionError (via verify_key_separation)
    """
    if state is None:
        raise SealNotFoundError(command.facility_id)
    if state.status is not SealStatus.LIVE:
        raise SealCannotRotateError(state.facility_id, state.status)
    if command.new_online_key_ref == state.online_key_ref:
        raise SealCannotRotateError(state.facility_id, state.status)

    if new_online_credential is None:
        raise CredentialNotFoundError(command.new_online_key_ref)
    if new_online_credential.purpose != CredentialPurpose.SEAL_ONLINE_SIGNING.value:
        raise SealKeyPurposeMismatchError(
            facility_id=state.facility_id,
            slot=_ONLINE_SLOT,
            credential_id=command.new_online_key_ref,
            expected_purpose=CredentialPurpose.SEAL_ONLINE_SIGNING.value,
            actual_purpose=new_online_credential.purpose,
        )
    if new_online_credential.facility_id != state.facility_id:
        raise SealCrossFacilityBindingError(
            expected_facility_id=state.facility_id,
            actual_facility_id=new_online_credential.facility_id,
            key_ref_role="online",
        )
    if new_online_credential.status != CredentialStatus.ACTIVE.value:
        raise SealCannotRotateWithInactiveCredentialError(
            facility_id=state.facility_id,
            slot=_ONLINE_SLOT,
            credential_id=command.new_online_key_ref,
            actual_status=new_online_credential.status,
        )

    prospective = replace(state, online_key_ref=command.new_online_key_ref)
    verify_key_separation(prospective)

    return [
        SealOnlineKeyRotated(
            facility_id=state.facility_id,
            new_online_key_ref=command.new_online_key_ref,
            signed_by_offline_root=command.signed_by_offline_root,
            rotated_by_actor_id=rotated_by_actor_id,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
