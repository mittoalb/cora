"""Pure decider for the `InitializeSeal` command.

Pure function: given the (always None) Seal state and an
`InitializeSeal` command, returns the events to append on the
Seal stream. No I/O, no awaits, no side effects.

`now` and `initialized_by_actor_id` are injected by the application
handler from the Clock port and the request envelope (non-determinism
principle: capture, don't recompute).

The cross-BC `DecisionRegistered` audit event on the Decision
stream is built directly by the handler (not by this decider) and
written atomically alongside the `SealInitialized` event via
`EventStore.append_streams`. Decider stays focused on the Seal
BC's domain invariants.

Invariants:
  - State must be None (genesis-only; Seal is a per-facility singleton)
    -> SealAlreadyExistsError
  - facility_id non-empty after trim
    -> InvalidSealFacilityIdError
  - online_key_ref != offline_key_ref (key-separation invariant;
    enforced by building the prospective post-state and calling
    `verify_key_separation` per sec-4 AH#15)
    -> SealKeyCollisionError

Cross-aggregate purpose binding (verifying each Credential.purpose
matches the slot) is deferred to a future iter pending a
CredentialLookup port; accepted opaquely today per the
eventual-consistency carve-out documented at
[[project_federation_port_design]].
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.seal import (
    InvalidSealFacilityIdError,
    Seal,
    SealAlreadyExistsError,
    SealInitialized,
    SealStatus,
    verify_key_separation,
)
from cora.federation.features.initialize_seal.command import InitializeSeal


def decide(
    state: Seal | None,
    command: InitializeSeal,
    *,
    now: datetime,
    initialized_by_actor_id: UUID,
) -> list[SealInitialized]:
    """Decide the events produced by initializing a Seal singleton."""
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
