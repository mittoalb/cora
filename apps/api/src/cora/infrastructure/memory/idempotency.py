"""In-memory `IdempotencyStore` for unit tests and the `test` app environment.

Mirrors the Postgres adapter's contract: same `(principal_id, key)`
namespacing, same first-writer-wins semantics on `put`. A
`threading.Lock` guards the dict so concurrent tasks see consistent
state. Not durable across process restarts (use the Postgres adapter
for production / integration).
"""

from threading import Lock
from uuid import UUID

from cora.infrastructure.ports.idempotency import CachedResult


class InMemoryIdempotencyStore:
    """Thread-safe in-memory implementation of the IdempotencyStore port."""

    def __init__(self) -> None:
        self._records: dict[tuple[UUID, str], CachedResult] = {}
        self._lock = Lock()

    async def get(self, principal_id: UUID, key: str) -> CachedResult | None:
        with self._lock:
            return self._records.get((principal_id, key))

    async def put(
        self,
        principal_id: UUID,
        key: str,
        record: CachedResult,
    ) -> None:
        with self._lock:
            # First-writer-wins: don't overwrite an existing key.
            self._records.setdefault((principal_id, key), record)
