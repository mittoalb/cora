"""Shared seed helpers for the Federation Permit lifecycle handler tests.

Each transition slice's handler test (activate / suspend / resume /
revoke) needs to seed a `Defined`, `Active`, `Suspended`, or `Revoked`
Permit against an InMemoryEventStore. The helpers keep per-test files
focused on assertions rather than re-encoding the same seed dance.
"""

from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.permit import (
    AbiTier,
    Direction,
    OnwardActionScope,
    OutboundTerms,
    PermitActivated,
    PermitDefined,
    PermitSuspended,
    ReadScope,
    ScopeRef,
    event_type_name,
    to_payload,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event


def _default_terms() -> OutboundTerms:
    return OutboundTerms(
        scope_set=frozenset({ScopeRef(kind="dataset", name="alpha")}),
        read_scope=ReadScope.READ_ALL_ARTIFACTS,
        onward_action_scope=OnwardActionScope.READ_ONLY,
    )


async def seed_defined_permit(
    store: InMemoryEventStore,
    *,
    permit_id: UUID,
    genesis_event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    defined_at: datetime,
    expires_at: datetime,
) -> None:
    """Append a single `PermitDefined` event to a fresh Permit stream."""
    genesis = PermitDefined(
        permit_id=permit_id,
        peer_facility_id="aps-2bm",
        direction=Direction.OUTBOUND,
        allowed_credentials=frozenset({UUID("01900000-0000-7000-8000-00000000c001")}),
        allowed_payload_types=frozenset({"application/vnd.cora.dataset+json"}),
        permitted_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=expires_at,
        defined_by_actor_id=principal_id,
        terms=_default_terms(),
        occurred_at=defined_at,
    )
    await store.append(
        stream_type="Permit",
        stream_id=permit_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(genesis),
                payload=to_payload(genesis),
                occurred_at=genesis.occurred_at,
                event_id=genesis_event_id,
                command_name="RegisterPermit",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


async def seed_active_permit(
    store: InMemoryEventStore,
    *,
    permit_id: UUID,
    genesis_event_id: UUID,
    activate_event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    defined_at: datetime,
    activated_at: datetime,
    expires_at: datetime,
) -> None:
    """Seed Defined then Activated; stream version ends at 2."""
    await seed_defined_permit(
        store,
        permit_id=permit_id,
        genesis_event_id=genesis_event_id,
        correlation_id=correlation_id,
        principal_id=principal_id,
        defined_at=defined_at,
        expires_at=expires_at,
    )
    activated = PermitActivated(
        permit_id=permit_id,
        activated_by_actor_id=principal_id,
        occurred_at=activated_at,
    )
    await store.append(
        stream_type="Permit",
        stream_id=permit_id,
        expected_version=1,
        events=[
            to_new_event(
                event_type=event_type_name(activated),
                payload=to_payload(activated),
                occurred_at=activated.occurred_at,
                event_id=activate_event_id,
                command_name="ActivatePermit",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


async def seed_suspended_permit(
    store: InMemoryEventStore,
    *,
    permit_id: UUID,
    genesis_event_id: UUID,
    activate_event_id: UUID,
    suspend_event_id: UUID,
    correlation_id: UUID,
    principal_id: UUID,
    defined_at: datetime,
    activated_at: datetime,
    suspended_at: datetime,
    expires_at: datetime,
) -> None:
    """Seed Defined then Activated then Suspended; stream version ends at 3."""
    await seed_active_permit(
        store,
        permit_id=permit_id,
        genesis_event_id=genesis_event_id,
        activate_event_id=activate_event_id,
        correlation_id=correlation_id,
        principal_id=principal_id,
        defined_at=defined_at,
        activated_at=activated_at,
        expires_at=expires_at,
    )
    suspended = PermitSuspended(
        permit_id=permit_id,
        suspended_by_actor_id=principal_id,
        occurred_at=suspended_at,
    )
    await store.append(
        stream_type="Permit",
        stream_id=permit_id,
        expected_version=2,
        events=[
            to_new_event(
                event_type=event_type_name(suspended),
                payload=to_payload(suspended),
                occurred_at=suspended.occurred_at,
                event_id=suspend_event_id,
                command_name="SuspendPermit",
                correlation_id=correlation_id,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


__all__ = [
    "seed_active_permit",
    "seed_defined_permit",
    "seed_suspended_permit",
]
