"""Projection-worker framework.

Public concepts:

  - `Projection` Protocol: the read-side fold a BC writes to maintain
    a `proj_<bc>_<name>` queryable table from the event stream. Per
    BC, lives in `cora.<bc>.projections.<name>`. The contract is
    documented on the Protocol itself.

  - `ProjectionRegistry`: the worker iterates this. Each BC registers
    its projections via a `register_<bc>_projections(registry, deps)`
    function the composition root calls during lifespan setup.

  - `projection_worker_lifespan(deps, registry, settings)`: async
    context manager the FastAPI lifespan wraps. Spawns the worker
    when the registry is non-empty + a Postgres pool is available;
    no-ops in the in-memory test environment.

  - `drain_projections(pool, registry, deadline_seconds)`: integration-
    test helper that synchronously advances every registered projection
    until each bookmark catches up to the head position (or raises
    `ProjectionDrainTimeoutError`). Avoids `asyncio.sleep` flakiness.

  - `encode_cursor` / `decode_cursor`: opaque base64 round-trip for
    `(created_at, UUID)` keyset-pagination cursors. Locked convention
    per Phase-8e D9: every `proj_*` table includes both columns; every
    list endpoint uses these helpers so cursor format is uniform across
    BCs.

Internal primitive: `Subscriber` Protocol (`worker.py`). Today every
Subscriber is a Projection; future sagas / external adapters will be
additional kinds of Subscriber sharing the same advance machinery.
Not exported publicly until a second Subscriber type lands.
"""

from cora.infrastructure.projection.cursor import (
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)
from cora.infrastructure.projection.drain import (
    ProjectionDrainTimeoutError,
    drain_projections,
)
from cora.infrastructure.projection.handler import Projection
from cora.infrastructure.projection.lifespan import projection_worker_lifespan
from cora.infrastructure.projection.registry import (
    DuplicateProjectionError,
    EmptySubscriptionError,
    ProjectionRegistry,
)

__all__ = [
    "DuplicateProjectionError",
    "EmptySubscriptionError",
    "InvalidCursorError",
    "Projection",
    "ProjectionDrainTimeoutError",
    "ProjectionRegistry",
    "decode_cursor",
    "drain_projections",
    "encode_cursor",
    "projection_worker_lifespan",
]
