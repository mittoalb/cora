"""Application handler for the `bind_plan_role` slice.

Custom (non-factory) update-style handler: loads Plan + Method +
Asset before reaching the pure decider, so the decider stays I/O-
free. Mirrors the multi-stream-load shape of `add_plan_wire`.

NOT idempotency-wrapped: bind is strict-not-idempotent at the
decider (`PlanRoleAlreadyBoundError`).
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import AssetNotFoundError
from cora.equipment.aggregates.asset.read import load_asset
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.method import MethodNotFoundError
from cora.recipe.aggregates.method.read import load_method
from cora.recipe.aggregates.plan import (
    PlanEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.bind_plan_role.command import BindPlanRole
from cora.recipe.features.bind_plan_role.context import BindPlanRoleContext
from cora.recipe.features.bind_plan_role.decider import decide

_STREAM_TYPE = "Plan"
_COMMAND_NAME = "BindPlanRole"
_LOG_PREFIX = "bind_plan_role"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every bind_plan_role handler implements."""

    async def __call__(
        self,
        command: BindPlanRole,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a bind_plan_role handler closed over the shared deps."""

    async def handler(
        command: BindPlanRole,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            f"{_LOG_PREFIX}.start",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            role_name=command.role_name.value,
            asset_id=str(command.asset_id),
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

        # Cross-aggregate loads: Method (via Plan.state.method_id) and
        # the candidate Asset. Both surface their respective NotFound
        # errors when the streams are empty.
        method = None
        if state is not None and state.method_id is not None:
            method = await load_method(deps.event_store, state.method_id)
            if method is None:
                raise MethodNotFoundError(state.method_id)

        asset = await load_asset(deps.event_store, command.asset_id)
        if asset is None:
            raise AssetNotFoundError(command.asset_id)

        context = BindPlanRoleContext(method=method, asset=asset)

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
            stream_id=command.plan_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            f"{_LOG_PREFIX}.success",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            role_name=command.role_name.value,
            asset_id=str(command.asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
