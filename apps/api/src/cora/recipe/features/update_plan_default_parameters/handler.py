"""Application handler for the `update_plan_default_parameters` slice.

Phase 6g-b. Update-style: load + fold + decide + append. NOT
idempotency-wrapped (no-op-on-unchanged at the decider; HTTP-layer
caching adds no value).

**Stays longhand (does NOT use a generic update-handler factory).**
This slice loads the Plan stream AND the owning Method stream
(needed for parameters_schema), so it can't share a single-stream
factory. Same posture as `update_asset_settings` (5g-c) which loads
the Asset and each assigned Family.

## Method-loading concurrency

Plan.method_id is folded onto state as of 6g-b (per the slim-aggregate
escape clause: state holds what future deciders need). The handler
loads the Method by that id concurrently is unnecessary — there's
exactly one Method per Plan, so a sequential load is just as fast.

If the Method id refers to a non-existent stream (eventual-
consistency stance — Plans can hold method_ids whose stream was
discarded) we pass None into the decider as parameters_schema.
Post-6g audit, the strict validator then rejects any non-empty
defaults with a clear "Method declares no parameters_schema"
error — operator's fix is to declare the Method properly OR omit
the defaults. Mirrors 5g-c's "no Capabilities + non-empty settings →
reject" anchor; see [[project_run_parameters_design]] §audit-correction.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.recipe.aggregates.method.read import load_method
from cora.recipe.aggregates.plan import (
    PlanEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.update_plan_default_parameters.command import (
    UpdatePlanDefaultParameters,
)
from cora.recipe.features.update_plan_default_parameters.decider import decide

_STREAM_TYPE = "Plan"
_COMMAND_NAME = "UpdatePlanDefaultParameters"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every update_plan_default_parameters handler implements."""

    async def __call__(
        self,
        command: UpdatePlanDefaultParameters,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an update_plan_default_parameters handler closed over the shared deps."""

    async def handler(
        command: UpdatePlanDefaultParameters,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> None:
        _log.info(
            "update_plan_default_parameters.start",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            key_count=len(command.default_parameters_patch),
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
                "update_plan_default_parameters.denied",
                command_name=_COMMAND_NAME,
                plan_id=str(command.plan_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.plan_id,
        )
        history: list[PlanEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        # Load the owning Method to surface its parameters_schema. If the
        # Plan doesn't exist (state is None) the decider raises
        # PlanNotFoundError before the schema is needed.
        method_parameters_schema = None
        if state is not None and state.method_id is not None:
            method = await load_method(deps.event_store, state.method_id)
            if method is not None:
                method_parameters_schema = method.parameters_schema

        domain_events = decide(
            state=state,
            command=command,
            method_parameters_schema=method_parameters_schema,
            now=now,
        )

        if not domain_events:
            _log.info(
                "update_plan_default_parameters.no_op",
                command_name=_COMMAND_NAME,
                plan_id=str(command.plan_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
            )
            return

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
            stream_id=command.plan_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "update_plan_default_parameters.success",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            key_count=len(command.default_parameters_patch),
            schema_present=method_parameters_schema is not None,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
