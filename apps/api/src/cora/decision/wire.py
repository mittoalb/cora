"""Compose the Decision BC's handlers from `SharedDeps`.

## BC-internal ReasoningStore wiring (gate-review L9)

The 8c-b `append_reasoning_entry` slice needs a `ReasoningStore`
adapter. Per the per-category-writer pattern locked at gate-review
L8 from 6f-5a (Conduit's TraversalStore), the store is built
LOCALLY here from `deps.pool` (Postgres in production) or as
`InMemoryReasoningStore` in `app_env=test`. NOT promoted to
SharedDeps fields. Mirrors how Trust BC wires its TraversalStore.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.decision.aggregates.decision import (
    InMemoryReasoningStore,
    PostgresReasoningStore,
    ReasoningStore,
)
from cora.decision.features import (
    append_reasoning_entry,
    get_decision,
    register_decision,
)
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.observability import with_tracing

_BC = "decision"


@dataclass(frozen=True)
class DecisionHandlers:
    """The Decision BC's handler bundle, each closed over SharedDeps."""

    register_decision: register_decision.IdempotentHandler
    get_decision: get_decision.Handler
    append_reasoning_entry: append_reasoning_entry.Handler


def wire_decision(deps: SharedDeps) -> DecisionHandlers:
    """Build the Decision BC handlers from shared dependencies."""
    reasoning_store: ReasoningStore = (
        PostgresReasoningStore(deps.pool) if deps.pool is not None else InMemoryReasoningStore()
    )
    return DecisionHandlers(
        register_decision=with_tracing(
            with_idempotency(
                register_decision.bind(deps),
                deps.idempotency_store,
                command_name="RegisterDecision",
                serialize_result=str,
                deserialize_result=UUID,
            ),
            command_name="RegisterDecision",
            bc=_BC,
        ),
        get_decision=with_tracing(
            get_decision.bind(deps),
            command_name="GetDecision",
            bc=_BC,
            kind="query",
        ),
        append_reasoning_entry=with_tracing(
            append_reasoning_entry.bind(deps, reasoning_store=reasoning_store),
            command_name="AppendReasoningEntry",
            bc=_BC,
        ),
    )
