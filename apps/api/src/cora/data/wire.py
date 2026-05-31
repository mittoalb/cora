"""Compose the Data BC's handlers from `Kernel`.

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

`register_dataset` is the create-style genesis (idempotency-wrapped).
The transitions (`discard`, `promote`, `demote`) are update-style
with bare handlers, strict-not-idempotent via their respective
`DatasetCannot*Error` / `DatasetAlready*Error` errors. `promote_dataset`
cross-loads peer Datasets via slice-local `DatasetPromotionContext` for the
lineage-must-be-Production guard; `demote_dataset` is the compensation
primitive and does no peer loads (no cross-BC cascade per
[[project-dataset-demote-design]] lock).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.data.features import (
    demote_dataset,
    discard_dataset,
    get_dataset,
    list_datasets,
    promote_dataset,
    register_dataset,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "data"


@dataclass(frozen=True)
class DataHandlers:
    """The Data BC's handler bundle, each closed over Kernel."""

    register_dataset: register_dataset.IdempotentHandler
    discard_dataset: discard_dataset.Handler
    promote_dataset: promote_dataset.Handler
    demote_dataset: demote_dataset.Handler
    get_dataset: get_dataset.Handler
    list_datasets: list_datasets.Handler


def wire_data(deps: Kernel) -> DataHandlers:
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
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="RegisterDataset",
            bc=_BC,
        ),
        discard_dataset=with_tracing(
            discard_dataset.bind(deps),
            command_name="DiscardDataset",
            bc=_BC,
        ),
        promote_dataset=with_tracing(
            promote_dataset.bind(deps),
            command_name="PromoteDataset",
            bc=_BC,
        ),
        demote_dataset=with_tracing(
            demote_dataset.bind(deps),
            command_name="DemoteDataset",
            bc=_BC,
        ),
        get_dataset=with_tracing(
            get_dataset.bind(deps),
            command_name="GetDataset",
            bc=_BC,
            kind="query",
        ),
        list_datasets=with_tracing(
            list_datasets.bind(deps),
            command_name="ListDatasets",
            bc=_BC,
            kind="query",
        ),
    )
