"""Idempotency-Key port: cache `(principal_id, key) -> cached result`.

Implements the IETF `Idempotency-Key` header pattern (Stripe / Adyen /
PayPal style). The application-layer decorator
`cora.access._idempotency.with_idempotency` wraps a command handler:
on retry with the same key, the cached result is returned without
re-executing the command.

Phase 2d ships single-phase semantics: get then put. This is correct
for a single-process server with sequential retries (the most common
case). Under genuinely concurrent retries (same key, simultaneous), two
handlers may both miss the cache and both execute — the underlying
event store will create two aggregates for create-style commands. The
production fix is two-phase (claim "in_progress" via INSERT, then
update "completed") per Stripe's pattern; deferred until real load
demands it.

Cached results are JSON-serializable forms of the handler's return
value (UUIDs become str, None stays null). Callers of the decorator
provide per-handler serialize/deserialize callables.
"""

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID


@dataclass(frozen=True)
class CachedResult:
    """A previously-completed command's stored result."""

    command_hash: str
    """SHA256 hex digest of canonical JSON of the command's dict form."""

    command_name: str
    """The command's dataclass name, e.g. 'RegisterActor'. For audit / debugging."""

    result: Any
    """JSON-serializable form of the handler's return value.

    UUIDs are stored as str. None is stored as null. The decorator's
    deserialize callable rebuilds the typed value on cache hit.
    """


class IdempotencyConflictError(Exception):
    """Same Idempotency-Key reused with a different command body.

    Per the IETF draft this is a client bug (a key MUST be tied to a
    single logical request). Mapped to HTTP 422 by the BC's exception
    handler.
    """

    def __init__(
        self,
        key: str,
        expected_hash: str,
        actual_hash: str,
    ) -> None:
        super().__init__(
            f"Idempotency-Key {key!r} was previously used with a different "
            f"request body (expected hash {expected_hash[:12]}..., "
            f"got {actual_hash[:12]}...)"
        )
        self.key = key
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash


class IdempotencyStore(Protocol):
    """Storage for `(principal_id, key) -> CachedResult` records."""

    async def get(
        self,
        principal_id: UUID,
        key: str,
    ) -> CachedResult | None:
        """Return the cached result for the given key, or None if absent."""
        ...

    async def put(
        self,
        principal_id: UUID,
        key: str,
        record: CachedResult,
    ) -> None:
        """Store a cached result. First-writer-wins on concurrent puts."""
        ...
