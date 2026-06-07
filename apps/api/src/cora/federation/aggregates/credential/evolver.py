"""Evolver: replay events to reconstruct Credential state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type is
added to `CredentialEvent` without a matching match arm here.

Status mapping per event type:
  - `CredentialRegistered`: status set to ACTIVE (genesis).
  - `CredentialRotationStarted`: status set to ROTATING (pending refs
    populated).
  - `CredentialRotationCompleted`: status set to ACTIVE (pending
    promoted to current).
  - `CredentialRotationAborted`: status set to ACTIVE (pending
    cleared).
  - `CredentialRevoked`: status set to REVOKED (terminal).

Source-state guards live at the decider, NOT here; the evolver trusts
the event log (folded events have already passed their decider).

Transition events applied to empty state raise `ValueError` via the
shared `require_state` helper at `cora.infrastructure.evolver`.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.federation.aggregates.credential.events import (
    CredentialEvent,
    CredentialRegistered,
    CredentialRevoked,
    CredentialRotationAborted,
    CredentialRotationCompleted,
    CredentialRotationStarted,
)
from cora.federation.aggregates.credential.state import (
    Credential,
    CredentialStatus,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Credential | None, event: CredentialEvent) -> Credential:
    """Apply one event to the current state."""
    match event:
        case CredentialRegistered(
            credential_id=credential_id,
            facility_id=facility_id,
            audience=audience,
            purpose=purpose,
            secret_ref=secret_ref,
            public_material_ref=public_material_ref,
            expires_at=expires_at,
            registered_by=registered_by,
            occurred_at=occurred_at,
        ):
            _ = state  # CredentialRegistered is the genesis event; prior state ignored
            return Credential(
                id=credential_id,
                facility_id=facility_id,
                audience=audience,
                purpose=purpose,
                secret_ref=secret_ref,
                public_material_ref=public_material_ref,
                expires_at=expires_at,
                registered_by=registered_by,
                registered_at=occurred_at,
                rotation_pending_secret_ref=None,
                rotation_pending_public_material_ref=None,
                status=CredentialStatus.ACTIVE,
            )
        case CredentialRotationStarted(
            pending_secret_ref=pending_secret_ref,
            pending_public_material_ref=pending_public_material_ref,
        ):
            prior = require_state(state, "CredentialRotationStarted")
            return Credential(
                id=prior.id,
                facility_id=prior.facility_id,
                audience=prior.audience,
                purpose=prior.purpose,
                secret_ref=prior.secret_ref,
                public_material_ref=prior.public_material_ref,
                expires_at=prior.expires_at,
                registered_by=prior.registered_by,
                registered_at=prior.registered_at,
                rotation_pending_secret_ref=pending_secret_ref,
                rotation_pending_public_material_ref=pending_public_material_ref,
                status=CredentialStatus.ROTATING,
            )
        case CredentialRotationCompleted():
            prior = require_state(state, "CredentialRotationCompleted")
            promoted_secret_ref = (
                prior.rotation_pending_secret_ref
                if prior.rotation_pending_secret_ref is not None
                else prior.secret_ref
            )
            promoted_public_material_ref = prior.rotation_pending_public_material_ref
            return Credential(
                id=prior.id,
                facility_id=prior.facility_id,
                audience=prior.audience,
                purpose=prior.purpose,
                secret_ref=promoted_secret_ref,
                public_material_ref=promoted_public_material_ref,
                expires_at=prior.expires_at,
                registered_by=prior.registered_by,
                registered_at=prior.registered_at,
                rotation_pending_secret_ref=None,
                rotation_pending_public_material_ref=None,
                status=CredentialStatus.ACTIVE,
            )
        case CredentialRotationAborted():
            prior = require_state(state, "CredentialRotationAborted")
            return Credential(
                id=prior.id,
                facility_id=prior.facility_id,
                audience=prior.audience,
                purpose=prior.purpose,
                secret_ref=prior.secret_ref,
                public_material_ref=prior.public_material_ref,
                expires_at=prior.expires_at,
                registered_by=prior.registered_by,
                registered_at=prior.registered_at,
                rotation_pending_secret_ref=None,
                rotation_pending_public_material_ref=None,
                status=CredentialStatus.ACTIVE,
            )
        case CredentialRevoked():
            prior = require_state(state, "CredentialRevoked")
            return Credential(
                id=prior.id,
                facility_id=prior.facility_id,
                audience=prior.audience,
                purpose=prior.purpose,
                secret_ref=prior.secret_ref,
                public_material_ref=prior.public_material_ref,
                expires_at=prior.expires_at,
                registered_by=prior.registered_by,
                registered_at=prior.registered_at,
                rotation_pending_secret_ref=prior.rotation_pending_secret_ref,
                rotation_pending_public_material_ref=prior.rotation_pending_public_material_ref,
                status=CredentialStatus.REVOKED,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[CredentialEvent]) -> Credential | None:
    """Replay a stream of events from the empty initial state."""
    state: Credential | None = None
    for event in events:
        state = evolve(state, event)
    return state
