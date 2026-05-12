"""Application handler for the `truncate_run` slice.

Update-style handler — three-field command (run_id + reason +
interrupted_at). Stays longhand for log-field clarity. Same shape as
`stop_run` modulo the extra `interrupted_at` field.

## Per-event grouping note (gate-review L11)

This handler emits one event today (`RunTruncated`); when the Run
aggregate gains logbooks (6f-5b/c), it will emit one
`RunLogbookClosed` per open logbook before the `RunTruncated`. All
events from one truncate command share:
  - the same `correlation_id` (the OTel trace_id)
  - `metadata.command = "TruncateRun"`
  - contiguous stream version order

Auditors group events from one truncate by `correlation_id` plus
`metadata.command`, NOT by `causation_id` (which is None for top-
level commands from REST/MCP).

## Liveness gap (gate-review L4-followup)

`truncate_run` is the cleanup mechanism for known-dead Runs; it
does NOT detect them. A Run that was interrupted on Saturday and
nobody truncates is still RUNNING in the FSM until an operator
calls truncate. Stale-RUNNING detection is a separate liveness
concern (heartbeat / projection-worker territory) and is out of
scope for 6f-4.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.run.aggregates.run import (
    RunEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.run.errors import UnauthorizedError
from cora.run.features.truncate_run.command import TruncateRun
from cora.run.features.truncate_run.decider import decide

_STREAM_TYPE = "Run"
_COMMAND_NAME = "TruncateRun"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every truncate_run handler implements."""

    async def __call__(
        self,
        command: TruncateRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a truncate_run handler closed over the shared deps."""

    async def handler(
        command: TruncateRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        _log.info(
            "truncate_run.start",
            command_name=_COMMAND_NAME,
            run_id=str(command.run_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            interrupted_at=(
                command.interrupted_at.isoformat() if command.interrupted_at is not None else None
            ),
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "truncate_run.denied",
                command_name=_COMMAND_NAME,
                run_id=str(command.run_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.run_id,
        )
        history: list[RunEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        domain_events = decide(state=state, command=command, now=now)

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=command.run_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "truncate_run.success",
            command_name=_COMMAND_NAME,
            run_id=str(command.run_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
