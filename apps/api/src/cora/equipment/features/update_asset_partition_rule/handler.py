"""Application handler for the `update_asset_partition_rule` slice.

Update-style handler: load + fold + decide + append. NOT
idempotency-wrapped (no-op-on-unchanged at the decider; HTTP-layer
caching adds no value).

The slice is self-gating on `Asset.partition_rule`: any Asset stream
that has had a rule set (or is being given one) is a virtual-axis
case. There is no separate Family-membership check; the `PseudoAxis`
Family entry in the closed catalog is retained as vocabulary but
plays no structural role here.

## Constituent asset loading (current limitation)

Current partition-rule shapes (Affine, Aggregation, LookupTable,
CompositePartition, SolverReference) do NOT carry constituent_asset_ids as
part of the rule. Constituents are inferred from Asset.ports input connections
at evaluator time. Therefore the handler does NOT load or validate
constituent assets here. Self-reference and nesting checks are a no-op here
and move to the runtime evaluator; they will be raised by the evaluator at
runtime if a future rule shape carries constituent_asset_ids.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import (
    AssetEvent,
    AssetNotFoundError,
    AssetPartitionRuleUpdated,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.update_asset_partition_rule.command import UpdateAssetPartitionRule
from cora.equipment.features.update_asset_partition_rule.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Asset"
_COMMAND_NAME = "UpdateAssetPartitionRule"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every update_asset_partition_rule handler implements."""

    async def __call__(
        self,
        command: UpdateAssetPartitionRule,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an update_asset_partition_rule handler closed over the shared deps."""

    async def handler(
        command: UpdateAssetPartitionRule,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "update_asset_partition_rule.start",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            partition_rule_kind=(
                command.partition_rule.kind.value if command.partition_rule is not None else None
            ),
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
                "update_asset_partition_rule.denied",
                command_name=_COMMAND_NAME,
                asset_id=str(command.asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.asset_id,
        )
        history: list[AssetEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        # Surface 404 before invoking the decider so a non-existent Asset
        # mis-surfaces as 404 rather than 409.
        if state is None:
            raise AssetNotFoundError(command.asset_id)

        domain_events: list[AssetPartitionRuleUpdated] = decide(
            state=state,
            command=command,
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
            stream_id=command.asset_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "update_asset_partition_rule.success",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            partition_rule_kind=(
                command.partition_rule.kind.value if command.partition_rule is not None else None
            ),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
