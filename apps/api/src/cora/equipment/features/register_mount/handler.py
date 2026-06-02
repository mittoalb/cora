"""Application handler for the `register_mount` slice.

Longhand create-style handler (cannot use a factory because it
loads a cross-aggregate projection BEFORE calling the decider for
slot_code uniqueness):

  1. Authz check (Deny -> UnauthorizedError).
  2. Load mount_slot_code projection -> existing_mount_id for slot_code.
  3. Call pure decider with state=None + context + command + now + new_id.
  4. Wrap emitted events and append to the Mount stream (single-
     stream write with expected_version=0 for genesis).

Pattern mirrors decommission_frame's longhand-with-precondition shape
but in the create-style (idempotency-wrapped at wire.py).
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.mount import event_type_name, to_payload
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.register_mount.command import RegisterMount
from cora.equipment.features.register_mount.context import RegisterMountContext
from cora.equipment.features.register_mount.decider import decide
from cora.equipment.projections.mount_slot_code import load_mount_id_by_slot_code
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Mount"
_COMMAND_NAME = "RegisterMount"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare register_mount handler - what `bind()` returns."""

    async def __call__(
        self,
        command: RegisterMount,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """register_mount handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RegisterMount,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a register_mount handler closed over the shared deps."""

    async def handler(
        command: RegisterMount,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "register_mount.start",
            command_name=_COMMAND_NAME,
            slot_code=command.slot_code,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "register_mount.denied",
                command_name=_COMMAND_NAME,
                slot_code=command.slot_code,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        # Projection precondition: is the slot_code already in use?
        existing_mount_id = await load_mount_id_by_slot_code(
            deps.pool,
            command.slot_code,
        )
        context = RegisterMountContext(existing_mount_id=existing_mount_id)

        domain_events = decide(
            state=None,
            command=command,
            context=context,
            now=now,
            new_id=new_id,
        )

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=new_id,
            expected_version=0,
            events=new_events,
        )

        _log.info(
            "register_mount.success",
            command_name=_COMMAND_NAME,
            mount_id=str(new_id),
            slot_code=command.slot_code,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            event_count=len(new_events),
        )
        return new_id

    return handler
