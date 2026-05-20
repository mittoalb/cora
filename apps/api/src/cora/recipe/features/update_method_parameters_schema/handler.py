"""Application handler for the `update_method_parameters_schema` slice.

Custom update-style handler (does NOT use the generic
`make_method_update_handler` factory): Phase 6l-strict-c adds a
cross-BC Capability load between Method-load and decide, so the
decider can enforce `Method.parameters_schema ⊆ Capability.parameter_schema`
without doing I/O itself.

The other Method update slices (version_method / deprecate_method)
keep using the generic factory since they have no cross-BC
dependency.

The command's `parameters_schema` is reduced to a `schema_present:
bool` for log-line diagnostic visibility (full schemas are
unsuitable for log lines; the event payload retains the schema).
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.capability import load_capability
from cora.recipe.aggregates.method import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.update_method_parameters_schema.command import (
    UpdateMethodParametersSchema,
)
from cora.recipe.features.update_method_parameters_schema.decider import decide

_STREAM_TYPE = "Method"
_COMMAND_NAME = "UpdateMethodParametersSchema"
_LOG_PREFIX = "update_method_parameters_schema"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every update_method_parameters_schema handler implements."""

    async def __call__(
        self,
        command: UpdateMethodParametersSchema,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an update_method_parameters_schema handler closed over the shared deps.

    Phase 6l-strict-c: between Method-load and decide we conditionally
    load the bound Recipe Capability (when the Method's `capability_id`
    is set) so the decider can run the cross-BC subset guard. When
    `capability_id` is None (pre-6l-strict Methods in lingering test
    fixtures or future un-bound code paths), `capability=None`
    passes through and the decider skips the subset check.
    """

    async def handler(
        command: UpdateMethodParametersSchema,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        schema_present = command.parameters_schema is not None
        _log.info(
            f"{_LOG_PREFIX}.start",
            command_name=_COMMAND_NAME,
            method_id=str(command.method_id),
            schema_present=schema_present,
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
                f"{_LOG_PREFIX}.denied",
                command_name=_COMMAND_NAME,
                method_id=str(command.method_id),
                schema_present=schema_present,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.method_id,
        )
        history = [from_stored(s) for s in stored]
        state = fold(history)

        # Phase 6l-strict-c: pre-load the bound Capability via the
        # cross-BC port when the Method declares one. The decider
        # raises `CapabilityNotFoundError` (404) if the stream is
        # missing, or `MethodParametersNotSubsetError` (409) if the
        # proposed schema isn't a subset.
        capability = None
        if state is not None and state.capability_id is not None:
            capability = await load_capability(deps.event_store, state.capability_id)

        domain_events = decide(state=state, command=command, capability=capability, now=now)

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
            stream_id=command.method_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            f"{_LOG_PREFIX}.success",
            command_name=_COMMAND_NAME,
            method_id=str(command.method_id),
            schema_present=schema_present,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )

    return handler
