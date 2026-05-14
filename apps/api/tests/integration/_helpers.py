"""Shared test helpers for integration tests against real Postgres.

Mirrors `tests/unit/_helpers.py::build_deps` but constructs a Kernel
backed by `PostgresEventStore` + `PostgresIdempotencyStore` over the
testcontainers `db_pool` fixture from `tests/integration/conftest.py`.

## Usage

```python
from tests.integration._helpers import build_postgres_deps

deps = build_postgres_deps(db_pool, ids=[method_id, event_id], now=_NOW)
deps = build_postgres_deps(db_pool, ids=[...], now=_NOW, authorize=RecordingAuthorize())
```

## Why a separate factory from the unit helper

Integration tests need PostgresEventStore + PostgresIdempotencyStore
constructed from the per-test `db_pool` fixture; unit tests use the
in-memory adapters with no pool. The two flows can't share a single
factory without either (a) optional pool with conditional adapter
selection (silently surprising) or (b) cross-tier imports (couples
test tiers).

`now` is required (no DEFAULT_NOW analog): integration tests pin a
per-test timestamp so the persisted event's `occurred_at` traces
back to the test that wrote it.
"""

from datetime import datetime
from uuid import UUID

import asyncpg

from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_postgres_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    Authorize,
    EventStore,
    FixedIdGenerator,
    FrozenClock,
    IdempotencyStore,
)


def build_postgres_deps(
    pool: asyncpg.Pool,
    *,
    now: datetime,
    ids: list[UUID] | None = None,
    authorize: Authorize | None = None,
    event_store: EventStore | None = None,
    idempotency_store: IdempotencyStore | None = None,
) -> Kernel:
    """Build a Kernel for integration-test handler invocation against real Postgres.

    Defaults: AllowAllAuthorize, fresh PostgresEventStore(pool), fresh
    PostgresIdempotencyStore(pool). Pass `event_store=` / `idempotency_store=`
    to share an already-constructed adapter (rare; useful when the test
    asserts state on a specific instance).

    `ids=` queues UUIDs for the FixedIdGenerator (handler consumes them
    in order: aggregate ids first, then event ids per emitted event).
    """
    return make_postgres_kernel(
        pool,
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(now),
        id_generator=FixedIdGenerator(list(ids or [])),
        authorize=authorize or AllowAllAuthorize(),
        event_store=event_store,
        idempotency_store=idempotency_store,
    )


__all__ = ["build_postgres_deps"]
