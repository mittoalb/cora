"""Compose the Decision BC's handlers from `Kernel`.

## BC-internal InferenceStore wiring

The `append_inferences` slice needs a `InferenceStore`
adapter. Per the per-category-writer pattern (Conduit's
VerdictStore precedent), the store is built LOCALLY here from
`deps.pool` (Postgres in production) or as
`InMemoryInferenceStore` in `app_env=test`. NOT promoted to
Kernel fields. Mirrors how Trust BC wires its VerdictStore.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.decision.aggregates.decision import (
    InferenceStore,
    InMemoryInferenceStore,
    PostgresInferenceStore,
)
from cora.decision.features import (
    append_inferences,
    get_decision,
    list_decisions,
    rate_decision,
    register_decision,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "decision"


@dataclass(frozen=True)
class DecisionHandlers:
    """The Decision BC's handler bundle, each closed over Kernel."""

    register_decision: register_decision.IdempotentHandler
    get_decision: get_decision.Handler
    list_decisions: list_decisions.Handler
    append_inferences: append_inferences.Handler
    rate_decision: rate_decision.Handler


def wire_decision(deps: Kernel) -> DecisionHandlers:
    """Build the Decision BC handlers from shared dependencies."""
    inference_store: InferenceStore = (
        PostgresInferenceStore(deps.pool) if deps.pool is not None else InMemoryInferenceStore()
    )
    return DecisionHandlers(
        register_decision=with_tracing(
            with_idempotency(
                register_decision.bind(deps),
                deps.idempotency_store,
                command_name="RegisterDecision",
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
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
        append_inferences=with_tracing(
            append_inferences.bind(deps, inference_store=inference_store),
            command_name="AppendInferences",
            bc=_BC,
        ),
        list_decisions=with_tracing(
            list_decisions.bind(deps),
            command_name="ListDecisions",
            bc=_BC,
            kind="query",
        ),
        rate_decision=with_tracing(
            rate_decision.bind(deps),
            command_name="RateDecision",
            bc=_BC,
        ),
    )
