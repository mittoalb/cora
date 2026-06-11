"""Application handler for the `register_edition` slice.

Genesis-style create handler mirroring `register_distribution` shape.
Pre-loads each member Dataset (same-BC) before invoking the pure
decider; missing ids raise `DatasetNotFoundError` upstream.

No `load_edition(new_id)`: `new_id` is freshly-allocated by the
IdGenerator port; the same-stream-id race at append time is caught
by Postgres `ConcurrencyError`.
"""

from typing import Protocol
from uuid import UUID

from cora.data.aggregates.dataset import (
    Dataset,
    DatasetNotFoundError,
    load_dataset,
)
from cora.data.aggregates.edition import event_type_name, to_payload
from cora.data.errors import UnauthorizedError
from cora.data.features.register_edition.command import RegisterEdition
from cora.data.features.register_edition.context import (
    EditionRegistrationContext,
)
from cora.data.features.register_edition.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Edition"
_COMMAND_NAME = "RegisterEdition"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare register_edition handler, what `bind()` returns."""

    async def __call__(
        self,
        command: RegisterEdition,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """register_edition handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: RegisterEdition,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a register_edition handler closed over the shared deps."""

    async def handler(
        command: RegisterEdition,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "register_edition.start",
            command_name=_COMMAND_NAME,
            kind=command.kind,
            dataset_count=len(command.dataset_ids),
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
                "register_edition.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Pre-load each member Dataset. Missing -> DatasetNotFoundError.
        datasets: dict[UUID, Dataset] = {}
        for dataset_id in command.dataset_ids:
            loaded = await load_dataset(deps.event_store, dataset_id)
            if loaded is None:
                raise DatasetNotFoundError(dataset_id)
            datasets[dataset_id] = loaded

        context = EditionRegistrationContext(datasets=datasets)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
            context=context,
            now=now,
            new_id=new_id,
            registered_by=ActorId(principal_id),
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
            "register_edition.success",
            command_name=_COMMAND_NAME,
            edition_id=str(new_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
