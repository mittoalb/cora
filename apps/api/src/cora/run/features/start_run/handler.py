"""Application handler for the `start_run` slice.

Eleventh instance of the create-style template body, second instance
that pre-loads upstream aggregate state (after `define_plan` in
6e-1). Per gate-review Q2 / Q5, this is the canonical pattern for
cross-aggregate validation in CORA.

## Pre-load order (Plan → Method via Practice → each bound Asset → Subject?)

1. `load_plan(plan_id)` → if None, `PlanNotFoundError`
2. `load_practice(plan.practice_id)` → if None, `PracticeNotFoundError`
   (defensive — Plan was bound against a real Practice; if Practice
   has somehow disappeared from the stream, that's serious corruption)
3. `load_method(practice.method_id)` → if None, `MethodNotFoundError`
4. For each `asset_id` in `plan.asset_ids`: `load_asset(asset_id)`
   → if None, `AssetNotFoundError` (Equipment-BC error, globally
   registered as 404 by Equipment's routes.py)
5. If `command.subject_id is not None`: `load_subject(subject_id)`
   → if None, `SubjectNotFoundError`

Loads run sequentially; could be optimized to async-gather later
but not the bottleneck at MVP scale.

The handler resolves `needs_capabilities` from the loaded Method
and passes it to the decider as a plain frozenset (so the decider
doesn't need a Method reference; cleaner separation). Decider
re-validates the capability superset against current Asset state
(gate-review Q5).

## What's NOT pre-loaded

Supply (Track B Supply BC not shipped) and Decision (Decision BC
not shipped) — documented gate-review Q3 gaps. Lands when those
BCs ship.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import Asset, AssetNotFoundError, load_asset
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.recipe.aggregates.method import MethodNotFoundError, load_method
from cora.recipe.aggregates.plan import PlanNotFoundError, load_plan
from cora.recipe.aggregates.practice import PracticeNotFoundError, load_practice
from cora.run.aggregates.run import event_type_name, to_payload
from cora.run.errors import UnauthorizedError
from cora.run.features.start_run.command import StartRun
from cora.run.features.start_run.context import RunStartContext
from cora.run.features.start_run.decider import decide
from cora.subject.aggregates.subject import SubjectNotFoundError, load_subject

_STREAM_TYPE = "Run"
_COMMAND_NAME = "StartRun"
_CONDUIT_DEFAULT_ID = UUID(int=0)

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare start_run handler — what `bind()` returns.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator wraps a bare Handler into an `IdempotentHandler`;
    production wiring in `wire.py` always wraps. Tests can use bare
    Handler directly when they don't need idempotency semantics.
    """

    async def __call__(
        self,
        command: StartRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """start_run handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: StartRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: SharedDeps) -> Handler:
    """Build a start_run handler closed over the shared deps."""

    async def handler(
        command: StartRun,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> UUID:
        _log.info(
            "start_run.start",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            subject_id=str(command.subject_id) if command.subject_id is not None else None,
            raid=command.raid,
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
                "start_run.denied",
                command_name=_COMMAND_NAME,
                plan_id=str(command.plan_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Pre-load cross-aggregate context (gate-review Q2 / Q5 pattern).
        plan = await load_plan(deps.event_store, command.plan_id)
        if plan is None:
            raise PlanNotFoundError(command.plan_id)

        practice = await load_practice(deps.event_store, plan.practice_id)
        if practice is None:
            # Defensive: Plan was bound against a real Practice; if
            # Practice has disappeared from the stream, that's serious
            # corruption. Surface as PracticeNotFoundError → 404.
            raise PracticeNotFoundError(plan.practice_id)

        method = await load_method(deps.event_store, practice.method_id)
        if method is None:
            raise MethodNotFoundError(practice.method_id)

        assets: dict[UUID, Asset] = {}
        for asset_id in sorted(plan.asset_ids, key=str):
            asset = await load_asset(deps.event_store, asset_id)
            if asset is None:
                raise AssetNotFoundError(asset_id)
            assets[asset_id] = asset

        subject = None
        if command.subject_id is not None:
            subject = await load_subject(deps.event_store, command.subject_id)
            if subject is None:
                raise SubjectNotFoundError(command.subject_id)

        context = RunStartContext(plan=plan, subject=subject, assets=assets)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
            context=context,
            needs_capabilities_snapshot=method.needs_capabilities,
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
            "start_run.success",
            command_name=_COMMAND_NAME,
            run_id=str(new_id),
            plan_id=str(command.plan_id),
            subject_id=str(command.subject_id) if command.subject_id is not None else None,
            method_id=str(method.id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler
