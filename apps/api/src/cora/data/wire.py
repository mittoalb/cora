"""Compose the Data BC's handlers from `SharedDeps`.

`wire_data(deps)` is invoked once from the FastAPI lifespan and the
returned `DataHandlers` bundle is stored on `app.state.data`. Routes
and MCP tools pull their handler out of that bundle. New slices add
a new field on `DataHandlers` and a single line in this factory.

Cross-cutting decorators applied here mirror every other BC
(composition order matters, innermost first):

1. `bind(deps)`: bare handler.
2. `with_idempotency` (create-style commands only): Idempotency-Key
   support. Wrapped before tracing so cache-hits and cache-misses
   both attribute to the tracing span.
3. `with_tracing`: OTel span around every handler call.

Phase 7a ships `register_dataset` (create-style; idempotency-
wrapped) and `get_dataset` (read side; no idempotency). Phase 7b
adds the `discard_dataset` transition (update-style; bare handler;
strict-not-idempotent so retries are domain-safe via
`DatasetCannotDiscardError`).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.data.features import discard_dataset, get_dataset, register_dataset
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.observability import with_tracing

_BC = "data"


@dataclass(frozen=True)
class DataHandlers:
    """The Data BC's handler bundle, each closed over SharedDeps.

    Phase 7a shipped `register_dataset` (create-style; idempotency-
    wrapped) plus `get_dataset` (read-side; no idempotency). Phase
    7b adds `discard_dataset` (update-style transition; bare handler).
    """

    register_dataset: register_dataset.IdempotentHandler
    discard_dataset: discard_dataset.Handler
    get_dataset: get_dataset.Handler


def wire_data(deps: SharedDeps) -> DataHandlers:
    """Build the Data BC handlers from shared dependencies."""
    return DataHandlers(
        register_dataset=with_tracing(
            with_idempotency(
                register_dataset.bind(deps),
                deps.idempotency_store,
                command_name="RegisterDataset",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
            ),
            command_name="RegisterDataset",
            bc=_BC,
        ),
        discard_dataset=with_tracing(
            discard_dataset.bind(deps),
            command_name="DiscardDataset",
            bc=_BC,
        ),
        get_dataset=with_tracing(
            get_dataset.bind(deps),
            command_name="GetDataset",
            bc=_BC,
            kind="query",
        ),
    )
