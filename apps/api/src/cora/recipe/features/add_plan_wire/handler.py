"""Application handler for the `add_plan_wire` slice.

Update-style handler that loads the Plan stream PLUS the Asset
streams the proposed wire references PLUS (when the target Asset
already has incoming wires) every SOURCE Asset of those existing
wires so the PseudoAxis fan-out validator can resolve source-port
signal_types without I/O. Stays longhand for the same reason
`update_plan_default_parameters` does (6g-b): it loads more than one
stream, so it can't share a single-stream factory.

NOT idempotency-wrapped: wire-mutation is strict-not-idempotent at
the decider (re-add raises `PlanWireAlreadyExistsError`); apply
only when cached-success-on-retry semantics are needed.

## Handler shape

  1. Authorize the principal for the `AddPlanWire` command.
  2. Load the Plan stream and fold to current state.
  3. Load the two Asset streams referenced by the proposed wire
     (deduped to one load when source_asset_id == target_asset_id),
     plus every SOURCE Asset of existing wires that already target
     the same Asset. Any reference that resolves to a non-existent
     Asset stream raises `AssetNotFoundError` (Equipment-BC error,
     404), matching `define_plan` and `start_procedure`. The decider's
     `PlanWireAssetNotBoundError` is retained as defense-in-depth
     for the case where an Asset exists but isn't in `Plan.asset_ids`.
  4. Load the Plan's bound Method so the decider can run the
     role-endpoint check.
  5. Pass state + context into the pure decider. PseudoAxis fan-out
     validation self-gates on `target_asset.partition_rule is not
     None`; no separate Family-membership lookup is needed.
  6. Persist the resulting events.

Mirrors the loading shape of `update_plan_default_parameters` (one
upstream-stream load alongside the target-aggregate load) but uses
the `PlanWireContext` (slice-local) to thread Asset state into the
decider in a typed way.
"""

from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import AssetNotFoundError
from cora.equipment.aggregates.asset.read import load_asset
from cora.infrastructure.event_envelope import to_new_event

if TYPE_CHECKING:
    from cora.equipment.aggregates.asset import Asset
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.method.read import load_method
from cora.recipe.aggregates.plan import (
    PlanEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.add_plan_wire.command import AddPlanWire
from cora.recipe.features.add_plan_wire.context import PlanWireContext
from cora.recipe.features.add_plan_wire.decider import decide

_STREAM_TYPE = "Plan"
_COMMAND_NAME = "AddPlanWire"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every add_plan_wire handler implements."""

    async def __call__(
        self,
        command: AddPlanWire,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an add_plan_wire handler closed over the shared deps."""

    async def handler(
        command: AddPlanWire,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "add_plan_wire.start",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            source_asset_id=str(command.source_asset_id),
            target_asset_id=str(command.target_asset_id),
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
                "add_plan_wire.denied",
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

        # Load the Assets referenced by the proposed wire (dedup the
        # self-loop case). Missing Asset streams raise
        # AssetNotFoundError (Equipment-BC error, 404), matching
        # define_plan and start_procedure. The decider's
        # PlanWireAssetNotBoundError stays in place as defense-in-
        # depth for Assets that exist but aren't bound to the Plan.
        asset_ids_to_load: set[UUID] = {
            command.source_asset_id,
            command.target_asset_id,
        }
        # When the target Asset already has incoming wires (other
        # sources fanning into the same target), pre-load each of
        # those source Assets too. The PseudoAxis fan-out validator
        # resolves source-side signal_types via assets_by_id and must
        # not perform I/O. Load these eagerly even before we know
        # whether the target is a PseudoAxis member: the cost is
        # bounded by the existing fan-in into the target Asset (zero
        # for non-PseudoAxis targets in practice) and avoids a second
        # round-trip after the family resolution.
        if state is not None:
            for existing in state.wires:
                if existing.target_asset_id == command.target_asset_id:
                    asset_ids_to_load.add(existing.source_asset_id)

        assets_by_id: dict[UUID, Asset] = {}
        for asset_id in sorted(asset_ids_to_load, key=str):
            asset = await load_asset(deps.event_store, asset_id)
            if asset is None:
                raise AssetNotFoundError(asset_id)
            assets_by_id[asset_id] = asset

        # Load the Plan's bound Method so the decider can run the
        # role-endpoint check (structural closure between role_bindings
        # and wires). When state.method_id is None
        # (legacy Plan) OR the Method stream is missing (eventual-
        # consistency reference; PlanDefined doesn't verify Method
        # existence at write time), the role check no-ops. This is
        # conservative: the role check is purely additive enforcement
        # of the wire-vs-role agreement; absence of Method state
        # means the agreement is vacuous (no roles can be declared).
        method = None
        if state is not None and state.method_id is not None:
            method = await load_method(deps.event_store, state.method_id)

        context = PlanWireContext(assets=assets_by_id, method=method)

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
            "add_plan_wire.success",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            source_asset_id=str(command.source_asset_id),
            target_asset_id=str(command.target_asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
