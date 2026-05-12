"""Application handler for the `define_plan` slice.

Tenth instance of the create-style template body, but with one
critical difference from the prior nine: this handler **pre-loads
upstream aggregate state** to build a `PlanBindingContext` before
calling the pure decider. Per gate-review Q5, this is the canonical
pattern for cross-aggregate validation in CORA.

## Pre-load order
1. `load_practice(practice_id)` → if None, raise `PracticeNotFoundError`
2. `load_method(practice.method_id)` → if None, raise `MethodNotFoundError`
3. For each `asset_id` in `command.asset_ids`: `load_asset(asset_id)`
   → if None, raise `AssetNotFoundError` (Equipment-BC error;
   already globally registered as 404 by Equipment's routes.py).

Loads run sequentially (Practice must complete before Method's id
is known; Asset loads are independent of each other but kept
sequential for 6e-1 simplicity — `asyncio.gather` is a future
optimization if profiling shows it matters).

The handler does NOT validate the loaded entities' state (Practice
not Deprecated, Asset not Decommissioned, capabilities cover
needs) — those checks belong in the pure decider. Handler is
responsible for *existence* (load returned non-None) and for
*assembling* the context; decider is responsible for *binding
validity*.

## Determinism caveat

Asset loads happen in sorted order of asset_id (stringified) so
two replays produce the same load sequence (relevant for tracing
spans and log correlation). The decider further sorts at event
construction time for payload determinism.

Module-as-namespace: callers use
`from cora.recipe.features import define_plan` then
`define_plan.bind(deps)` returning a `define_plan.Handler`.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import Asset, AssetNotFoundError, load_asset
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.recipe.aggregates.method import MethodNotFoundError, load_method
from cora.recipe.aggregates.plan import event_type_name, to_payload
from cora.recipe.aggregates.practice import PracticeNotFoundError, load_practice
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.define_plan.command import DefinePlan
from cora.recipe.features.define_plan.context import PlanBindingContext
from cora.recipe.features.define_plan.decider import decide

_STREAM_TYPE = "Plan"
_COMMAND_NAME = "DefinePlan"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare define_plan handler — what `bind()` returns.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator wraps a bare Handler into an `IdempotentHandler`;
    production wiring in `wire.py` always wraps. Tests can use bare
    Handler directly when they don't need idempotency semantics.

    `causation_id` is the id of the event/message that triggered
    this command (None for HTTP / MCP root calls; sagas / process
    managers pass the upstream event's id).
    """

    async def __call__(
        self,
        command: DefinePlan,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """define_plan handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: DefinePlan,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a define_plan handler closed over the shared deps."""

    async def handler(
        command: DefinePlan,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> UUID:
        _log.info(
            "define_plan.start",
            command_name=_COMMAND_NAME,
            practice_id=str(command.practice_id),
            asset_count=len(command.asset_ids),
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
                "define_plan.denied",
                command_name=_COMMAND_NAME,
                practice_id=str(command.practice_id),
                asset_count=len(command.asset_ids),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Pre-load cross-aggregate context (gate-review Q5 pattern).
        practice = await load_practice(deps.event_store, command.practice_id)
        if practice is None:
            raise PracticeNotFoundError(command.practice_id)

        method = await load_method(deps.event_store, practice.method_id)
        if method is None:
            raise MethodNotFoundError(practice.method_id)

        assets: dict[UUID, Asset] = {}
        for asset_id in sorted(command.asset_ids, key=str):
            asset = await load_asset(deps.event_store, asset_id)
            if asset is None:
                raise AssetNotFoundError(asset_id)
            assets[asset_id] = asset

        context = PlanBindingContext(practice=practice, method=method, assets=assets)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

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
            "define_plan.success",
            command_name=_COMMAND_NAME,
            plan_id=str(new_id),
            practice_id=str(command.practice_id),
            method_id=str(method.id),
            asset_count=len(command.asset_ids),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
