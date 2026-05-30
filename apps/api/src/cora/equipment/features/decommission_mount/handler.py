"""Application handler for the `decommission_mount` slice.

Longhand handler (cannot use make_mount_update_handler because it
loads a cross-aggregate projection BEFORE calling the decider):
loads active child mount IDs from mount_children projection,
packages them into context, calls the pure decider with state +
context.

Single-stream-write + projection-precondition pattern (mirrors
decommission_frame). The same eventual-consistency caveat applies:
projection read and Mount stream append are not in one serializable
txn; a child registered in the window between read and append could
leave the parent Decommissioned with an active child. Acceptable
for v1 (rare operation, small window, observable inconsistency);
promote to SERIALIZABLE or PG advisory lock at first incident.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.mount import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.decommission_mount.command import DecommissionMount
from cora.equipment.features.decommission_mount.context import DecommissionMountContext
from cora.equipment.features.decommission_mount.decider import decide
from cora.equipment.projections.mount_children import load_active_mount_children
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Mount"
_COMMAND_NAME = "DecommissionMount"

_log = get_logger(__name__)


class Handler(Protocol):
    async def __call__(
        self,
        command: DecommissionMount,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    async def handler(
        command: DecommissionMount,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "decommission_mount.start",
            command_name=_COMMAND_NAME,
            mount_id=str(command.mount_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "decommission_mount.denied",
                command_name=_COMMAND_NAME,
                mount_id=str(command.mount_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        # Load Mount stream + fold to current state (version comes
        # from load() directly; load_mount discards the version).
        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.mount_id,
        )
        history = [from_stored(s) for s in stored]
        state = fold(history)

        # Projection precondition: which child Mounts currently
        # reference this parent? Loaded BEFORE the decider so the
        # pure decider raises MountHasActiveChildrenError without I/O.
        active_child_mount_ids = await load_active_mount_children(
            deps.pool,
            command.mount_id,
        )
        context = DecommissionMountContext(active_child_mount_ids=active_child_mount_ids)

        domain_events = decide(
            state=state,
            command=command,
            context=context,
            now=now,
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
            stream_id=command.mount_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "decommission_mount.success",
            command_name=_COMMAND_NAME,
            mount_id=str(command.mount_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
