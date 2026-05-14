"""End-to-end integration test: promote_dataset against real Postgres (Phase 7e).

Standalone-upload Dataset (no producing_run, no derived_from): the
simplest end-to-end path that exercises promote_dataset's full
round-trip through the PG event store. Verifies:

  - DatasetPromoted event lands in the stream
  - load_dataset folds back with intent == Production
  - Re-promote raises DatasetAlreadyPromotedError (strict-not-idempotent
    over a real PG round-trip, not just the in-memory store)
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DatasetAlreadyPromotedError,
    Intent,
    load_dataset,
)
from cora.data.features import promote_dataset, register_dataset
from cora.data.features.promote_dataset import PromoteDataset
from cora.data.features.register_dataset import RegisterDataset
from cora.infrastructure.kernel import Kernel
from tests.integration._helpers import build_postgres_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _register_standalone_dataset(deps: Kernel) -> UUID:
    """Register a standalone-upload Dataset (no producing_run, no
    derived_from)."""
    return await register_dataset.bind(deps)(
        RegisterDataset(
            name="standalone-upload",
            uri="s3://bucket/key",
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA256,
            byte_size=0,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
            producing_run_id=None,
            subject_id=None,
            derived_from=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_promote_dataset_round_trips_event_against_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Full end-to-end: register a standalone Dataset, promote it,
    fold-on-read returns Intent.PRODUCTION."""
    deps = _build_deps(db_pool, [uuid4(), uuid4(), uuid4()])  # register + promote event ids

    dataset_id = await _register_standalone_dataset(deps)

    # Verify intent defaults to Trial after registration.
    after_register = await load_dataset(deps.event_store, dataset_id)
    assert after_register is not None
    assert after_register.intent is Intent.TRIAL

    # Promote it.
    await promote_dataset.bind(deps)(
        PromoteDataset(dataset_id=dataset_id, reason="passed peer review"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Verify intent flipped to Production via real PG round-trip.
    after_promote = await load_dataset(deps.event_store, dataset_id)
    assert after_promote is not None
    assert after_promote.intent is Intent.PRODUCTION


@pytest.mark.integration
async def test_re_promote_raises_already_promoted_against_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Strict-not-idempotent enforced over real PG round-trip."""
    deps = _build_deps(db_pool, [uuid4(), uuid4(), uuid4()])

    dataset_id = await _register_standalone_dataset(deps)

    # First promote succeeds.
    await promote_dataset.bind(deps)(
        PromoteDataset(dataset_id=dataset_id, reason="passed review"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Second promote raises.
    with pytest.raises(DatasetAlreadyPromotedError):
        await promote_dataset.bind(deps)(
            PromoteDataset(dataset_id=dataset_id, reason="trying again"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
