"""Cross-cutting idempotency decorator for Access command handlers.

`with_idempotency(handler, store, *, command_name, serialize_result,
deserialize_result)` returns a wrapped handler with Idempotency-Key
support. The wrap is applied in `wire.py` so every command handler
gets idempotency through one composition point — slices stay focused
on domain logic.

Single-phase semantics (Phase 2d MVP): on each call with a key, look
up the cache; if hit and the command hash matches, return the cached
result; if hit but the hash differs, raise IdempotencyConflictError
(mapped to HTTP 422); if miss, execute the handler and cache the
result. Race condition under genuinely concurrent retries (same key,
two parallel requests both miss) is documented in the IdempotencyStore
port docstring; production fix is two-phase claim/complete per Stripe.

Hashing: commands are frozen dataclasses with primitive fields.
`hash_command(cmd)` serializes via `asdict` + `json.dumps(sort_keys=True,
default=str)` + SHA256. The `default=str` defangs UUIDs and datetimes
that may appear in command fields.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict
from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.ports import (
    CachedResult,
    IdempotencyConflictError,
    IdempotencyStore,
)


def hash_command(command: Any) -> str:
    """SHA256 hex digest of canonical JSON of the command's dict form."""
    canonical = json.dumps(asdict(command), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class _BareHandler[TCommand, TResult](Protocol):
    async def __call__(
        self,
        command: TCommand,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> TResult: ...


class _IdempotentHandler[TCommand, TResult](Protocol):
    async def __call__(
        self,
        command: TCommand,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        idempotency_key: str | None = None,
    ) -> TResult: ...


def with_idempotency[TCommand, TResult](
    handler: _BareHandler[TCommand, TResult],
    store: IdempotencyStore,
    *,
    command_name: str,
    serialize_result: Callable[[TResult], Any],
    deserialize_result: Callable[[Any], TResult],
) -> _IdempotentHandler[TCommand, TResult]:
    """Wrap a bare command handler with Idempotency-Key support."""

    async def wrapped(
        command: TCommand,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        idempotency_key: str | None = None,
    ) -> TResult:
        if idempotency_key is None:
            return await handler(
                command,
                principal_id=principal_id,
                correlation_id=correlation_id,
            )

        cmd_hash = hash_command(command)
        cached = await store.get(principal_id, idempotency_key)
        if cached is not None:
            if cached.command_hash != cmd_hash:
                raise IdempotencyConflictError(
                    key=idempotency_key,
                    expected_hash=cached.command_hash,
                    actual_hash=cmd_hash,
                )
            return deserialize_result(cached.result)

        result = await handler(
            command,
            principal_id=principal_id,
            correlation_id=correlation_id,
        )
        await store.put(
            principal_id,
            idempotency_key,
            CachedResult(
                command_hash=cmd_hash,
                command_name=command_name,
                result=serialize_result(result),
            ),
        )
        return result

    return wrapped


__all__ = [
    "hash_command",
    "with_idempotency",
]
