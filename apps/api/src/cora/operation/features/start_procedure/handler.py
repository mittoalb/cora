"""Application handler for the `start_procedure` slice.

Update-style handler with a custom body (NOT the update-handler
factory): the start_procedure flow pre-loads the target Assets to
build a `ProcedureStartContext` for the decider's Decommissioned
guard. The factory at `cora.infrastructure.update_handler` doesn't
support cross-aggregate context loads; same reason `start_run`'s
handler is custom.

## Pre-load order

1. `load_procedure(procedure_id)` -> if None, `ProcedureNotFoundError`
2. For each `asset_id` in `procedure.target_asset_ids`:
   `load_asset(asset_id)` -> if None, `AssetNotFoundError` (Equipment-
   BC error, globally registered as 404 by Equipment's routes.py)

Loads run sequentially; could be optimized to async-gather later but
not the bottleneck at MVP scale (target_asset_ids is small for any
realistic procedure: typically 1-5).

## What's NOT pre-loaded

Supply (Supply BC integration deferred per
[[project_operation_design]]) and Decision (Decision BC integration
deferred). Documented as known gaps.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import Asset, AssetNotFoundError, load_asset
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.operation.aggregates.procedure import (
    ProcedureNotFoundError,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.operation.errors import UnauthorizedError
from cora.operation.features.start_procedure.command import StartProcedure
from cora.operation.features.start_procedure.context import ProcedureStartContext
from cora.operation.features.start_procedure.decider import decide

_STREAM_TYPE = "Procedure"
_COMMAND_NAME = "StartProcedure"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare start_procedure handler -- what `bind()` returns."""

    async def __call__(
        self,
        command: StartProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


class IdempotentHandler(Protocol):
    """start_procedure handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: StartProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a start_procedure handler closed over the shared deps."""

    async def handler(
        command: StartProcedure,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "start_procedure.start",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
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
                "start_procedure.denied",
                command_name=_COMMAND_NAME,
                procedure_id=str(command.procedure_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        stored, version = await deps.event_store.load(_STREAM_TYPE, command.procedure_id)
        state = fold([from_stored(s) for s in stored])
        if state is None:
            raise ProcedureNotFoundError(command.procedure_id)

        assets: dict[UUID, Asset] = {}
        for asset_id in sorted(state.target_asset_ids, key=str):
            asset = await load_asset(deps.event_store, asset_id)
            if asset is None:
                raise AssetNotFoundError(asset_id)
            assets[asset_id] = asset

        context = ProcedureStartContext(assets=assets)

        now = deps.clock.now()
        domain_events = decide(state=state, command=command, context=context, now=now)

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
            stream_id=command.procedure_id,
            expected_version=version,
            events=new_events,
        )

        _log.info(
            "start_procedure.success",
            command_name=_COMMAND_NAME,
            procedure_id=str(command.procedure_id),
            target_asset_count=len(assets),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )

    return handler
