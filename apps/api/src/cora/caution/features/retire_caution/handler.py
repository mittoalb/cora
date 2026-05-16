"""Application handler for the `retire_caution` slice.

Update-style handler. Per the design memo and
[[project_update_handler_pattern]], `make_caution_update_handler`
factory is NOT hoisted at 11b-a: rule-of-three has not fired
(only one update slice ships in 11b-a: retire). The factory will
likely emerge when `amend_text` or a future transition slice lands;
until then this slice carries the full longhand body for clarity.

Not idempotency-wrapped: transition handlers use the
strict-not-idempotent guard at the decider (re-retiring an already-
Retired caution raises `CautionCannotRetireError` -> HTTP 409);
HTTP-layer caching adds no value for transitions.
"""

from typing import Protocol
from uuid import UUID

from cora.caution.aggregates.caution import (
    CautionNotFoundError,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.caution.aggregates.caution.evolver import fold
from cora.caution.errors import UnauthorizedError
from cora.caution.features.retire_caution.command import RetireCaution
from cora.caution.features.retire_caution.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny

_STREAM_TYPE = "Caution"
_COMMAND_NAME = "RetireCaution"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every retire_caution handler implements."""

    async def __call__(
        self,
        command: RetireCaution,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a retire_caution handler closed over the shared deps."""

    async def handler(
        command: RetireCaution,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        _log.info(
            "retire_caution.start",
            command_name=_COMMAND_NAME,
            caution_id=str(command.caution_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=_CONDUIT_DEFAULT_ID,
        )
        if isinstance(decision, Deny):
            _log.info(
                "retire_caution.denied",
                command_name=_COMMAND_NAME,
                caution_id=str(command.caution_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, version = await deps.event_store.load(_STREAM_TYPE, command.caution_id)
        if version == 0:
            raise CautionNotFoundError(command.caution_id)
        events = [from_stored(s) for s in stored]
        state = fold(events)
        if state is None:  # pragma: no cover  # version > 0 implies state non-None
            raise CautionNotFoundError(command.caution_id)

        now = deps.clock.now()
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
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=command.caution_id,
            expected_version=version,
            events=new_events,
        )

        _log.info(
            "retire_caution.success",
            command_name=_COMMAND_NAME,
            caution_id=str(command.caution_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )

    return handler
