"""Pure decider for the `InitializeSeal` command.

Pure function: given the (always None) Seal state and an
`InitializeSeal` command plus two `CredentialLookupResult` snapshots
(one per slot), returns the events to append on the Seal stream. No
I/O, no awaits, no side effects.

`now` and `initialized_by_actor_id` are injected by the application
handler from the Clock port and the request envelope (non-determinism
principle: capture, don't recompute).

`online_credential` and `offline_credential` are likewise handler-
injected: the handler resolves each ref via the `CredentialLookup`
port BEFORE invoking the decider, and the decider partitions on the
`purpose` / `status` of each projection row. Mirrors the
`rotate_seal_online_key` precedent (Pass 2) and the `start_run`
pattern (handler loads upstream projections, threads them into the
pure decider). The decider stays pure: no I/O, no await.

The cross-BC `DecisionRegistered` audit event on the Decision
stream is built directly by the handler (not by this decider) and
written atomically alongside the `SealInitialized` event via
`EventStore.append_streams`. Decider stays focused on the Seal
BC's domain invariants.

## Validation

  - State must be None (genesis-only; Seal is a per-facility singleton)
    -> SealAlreadyExistsError
  - facility_id non-empty after trim
    -> InvalidSealFacilityIdError
  - online_key_ref != offline_key_ref (key-separation invariant;
    enforced by building the prospective post-state and calling
    `verify_key_separation` per sec-4 AH#15)
    -> SealKeyCollisionError
  - online_credential must not be None (projection must know the ref)
    -> CredentialNotFoundError (per the start_run -> PlanNotFoundError
    precedent)
  - offline_credential must not be None
    -> CredentialNotFoundError
  - online_credential.purpose must equal "SealOnlineSigning"
    -> SealKeyPurposeMismatchError (HTTP 422)
  - offline_credential.purpose must equal "SealOfflineRoot"
    -> SealKeyPurposeMismatchError (HTTP 422)
  - online_credential.status must equal "Active"
    -> SealCannotInitializeWithInactiveCredentialError (HTTP 409;
    Rotating or Revoked secrets cannot back a Seal)
  - offline_credential.status must equal "Active"
    -> SealCannotInitializeWithInactiveCredentialError (HTTP 409)
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.credential import (
    CredentialNotFoundError,
    CredentialPurpose,
    CredentialStatus,
)
from cora.federation.aggregates.seal import (
    InvalidSealFacilityIdError,
    Seal,
    SealAlreadyExistsError,
    SealCannotInitializeWithInactiveCredentialError,
    SealInitialized,
    SealKeyPurposeMismatchError,
    SealStatus,
    verify_key_separation,
)
from cora.federation.features.initialize_seal.command import InitializeSeal
from cora.infrastructure.ports.credential_lookup import CredentialLookupResult

_ONLINE_SLOT = "online_key_ref"
_OFFLINE_SLOT = "offline_key_ref"


def decide(
    state: Seal | None,
    command: InitializeSeal,
    *,
    now: datetime,
    initialized_by_actor_id: UUID,
    online_credential: CredentialLookupResult | None,
    offline_credential: CredentialLookupResult | None,
) -> list[SealInitialized]:
    """Decide the events produced by initializing a Seal singleton.

    Invariants:
      - State must be None (genesis-only singleton)
        -> SealAlreadyExistsError
      - facility_id non-empty after trim
        -> InvalidSealFacilityIdError
      - online_key_ref must differ from offline_key_ref
        -> SealKeyCollisionError (via verify_key_separation)
      - online_credential must not be None
        -> CredentialNotFoundError (unknown credential ref)
      - offline_credential must not be None
        -> CredentialNotFoundError (unknown credential ref)
      - online_credential.purpose must be SealOnlineSigning
        -> SealKeyPurposeMismatchError
      - offline_credential.purpose must be SealOfflineRoot
        -> SealKeyPurposeMismatchError
      - online_credential.status must be Active
        -> SealCannotInitializeWithInactiveCredentialError
      - offline_credential.status must be Active
        -> SealCannotInitializeWithInactiveCredentialError
    """
    if state is not None:
        raise SealAlreadyExistsError(state.facility_id)

    facility_id = command.facility_id.strip()
    if not facility_id:
        raise InvalidSealFacilityIdError(command.facility_id)

    prospective = Seal(
        facility_id=facility_id,
        online_key_ref=command.online_key_ref,
        offline_key_ref=command.offline_key_ref,
        current_head_hash=None,
        current_sequence_number=0,
        initialized_by_actor_id=initialized_by_actor_id,
        status=SealStatus.LIVE,
    )
    verify_key_separation(prospective)

    if online_credential is None:
        raise CredentialNotFoundError(command.online_key_ref)
    if offline_credential is None:
        raise CredentialNotFoundError(command.offline_key_ref)

    if online_credential.purpose != CredentialPurpose.SEAL_ONLINE_SIGNING.value:
        raise SealKeyPurposeMismatchError(
            facility_id=facility_id,
            slot=_ONLINE_SLOT,
            credential_id=command.online_key_ref,
            expected_purpose=CredentialPurpose.SEAL_ONLINE_SIGNING.value,
            actual_purpose=online_credential.purpose,
        )
    if offline_credential.purpose != CredentialPurpose.SEAL_OFFLINE_ROOT.value:
        raise SealKeyPurposeMismatchError(
            facility_id=facility_id,
            slot=_OFFLINE_SLOT,
            credential_id=command.offline_key_ref,
            expected_purpose=CredentialPurpose.SEAL_OFFLINE_ROOT.value,
            actual_purpose=offline_credential.purpose,
        )

    if online_credential.status != CredentialStatus.ACTIVE.value:
        raise SealCannotInitializeWithInactiveCredentialError(
            facility_id=facility_id,
            slot=_ONLINE_SLOT,
            credential_id=command.online_key_ref,
            actual_status=online_credential.status,
        )
    if offline_credential.status != CredentialStatus.ACTIVE.value:
        raise SealCannotInitializeWithInactiveCredentialError(
            facility_id=facility_id,
            slot=_OFFLINE_SLOT,
            credential_id=command.offline_key_ref,
            actual_status=offline_credential.status,
        )

    return [
        SealInitialized(
            facility_id=facility_id,
            online_key_ref=command.online_key_ref,
            offline_key_ref=command.offline_key_ref,
            initialized_by_actor_id=initialized_by_actor_id,
            occurred_at=now,
        )
    ]


__all__ = ["decide"]
