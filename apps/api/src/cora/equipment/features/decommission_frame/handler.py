"""Application handler for the `decommission_frame` slice.

Longhand handler (cannot use `make_frame_update_handler` because it
loads a cross-aggregate projection BEFORE calling the decider):

  1. Authz check (Deny -> UnauthorizedError).
  2. Load + fold Frame stream (None -> FrameNotFoundError via decider).
  3. Load active frame_consumers via projection precondition.
  4. Call pure decider with state + context + command + now.
  5. Wrap emitted events and append to the Frame stream (single-
     stream write; the asset_location / mount_children / etc.
     projections observe the FrameDecommissioned event and update
     themselves).

Pattern: single-stream-write + projection-precondition (Visit BC
`take_control_of_surface` precedent). `append_streams` is NOT used
here because Mount + Asset are intra-BC observers, not cross-BC
event participants.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.frame import (
    event_type_name,
    load_frame,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.decommission_frame.command import DecommissionFrame
from cora.equipment.features.decommission_frame.context import DecommissionFrameContext
from cora.equipment.features.decommission_frame.decider import decide
from cora.equipment.projections.frame_consumers import load_active_frame_consumers
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Frame"
_COMMAND_NAME = "DecommissionFrame"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every decommission_frame handler implements."""

    async def __call__(
        self,
        command: DecommissionFrame,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a decommission_frame handler closed over the shared deps."""

    async def handler(
        command: DecommissionFrame,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "decommission_frame.start",
            command_name=_COMMAND_NAME,
            frame_id=str(command.frame_id),
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
                "decommission_frame.denied",
                command_name=_COMMAND_NAME,
                frame_id=str(command.frame_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        # Load + fold the Frame stream so we have an authoritative
        # version for the optimistic append below.
        state = await load_frame(deps.event_store, command.frame_id)
        # The version returned by load_frame's underlying load() call
        # is what we pass to append; load_frame discards it (it only
        # returns the folded state), so call load() directly here too
        # for the version. Two reads against the same stream are
        # cheap and the cleaner shape; refactor when load_frame
        # surfaces both if a pattern emerges across slices.
        _stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.frame_id,
        )

        # Projection precondition: which Mount/Frame consumers
        # currently reference this frame? Loaded BEFORE the decider
        # so the pure decider raises FrameInUseError without I/O.
        #
        # Known race: the projection read and the Frame stream append
        # are NOT serializable as one txn. Between this read and the
        # append on line 143, a new child Frame could register against
        # this parent and its projection write could land in the
        # window, leaving the parent Decommissioned with an active
        # child. Acceptable for v1: decommissions are rare, the race
        # window is small, and the surviving inconsistency is
        # observable (the orphaned child's parent is gone) and
        # operationally recoverable. Promote to SERIALIZABLE or a
        # PG advisory lock when first incident report shows the race
        # firing in production.
        # Pool-None short-circuit preserves the pre-tightening permissive
        # default (no consumers) for the pool-less test path; in
        # production deps.pool is always set.
        active_consumer_ids = (
            await load_active_frame_consumers(deps.pool, command.frame_id)
            if deps.pool is not None
            else ()
        )
        context = DecommissionFrameContext(active_consumer_ids=active_consumer_ids)

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
            stream_id=command.frame_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "decommission_frame.success",
            command_name=_COMMAND_NAME,
            frame_id=str(command.frame_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
