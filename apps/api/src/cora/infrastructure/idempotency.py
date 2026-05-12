"""Cross-cutting idempotency decorator for command handlers.

`with_idempotency(handler, store, *, command_name, serialize_result,
deserialize_result)` returns a wrapped handler with Idempotency-Key
support. The wrap is applied in each BC's `wire.py` so every create-
style command handler gets idempotency through one composition point;
slices stay focused on domain logic.

Lives at `cora/infrastructure/` (not in any single BC) because it
applies uniformly to every BC's command handlers and depends only on
the IdempotencyStore port + the cross-BC handler-call convention
(`(command, *, principal_id, correlation_id, causation_id) -> TResult`).
The Access BC was the first consumer; Trust is the second; the file
moved out of `cora/access/` when the second consumer landed, per the
BC-2-trigger note in CONTRIBUTING.md.

Single-phase semantics (Phase 2d MVP): on each call with a key, look
up the cache; if hit and the command hash matches, return the cached
result; if hit but the hash differs, raise IdempotencyConflictError
(mapped to HTTP 422); if miss, execute the handler and cache the
result. Race condition under genuinely concurrent retries (same key,
two parallel requests both miss) is documented in the IdempotencyStore
port docstring; production fix is two-phase claim/complete per Stripe.

Hashing: commands MUST be frozen dataclasses (with primitive or nested-
dataclass fields). `hash_command(cmd)` serializes via `asdict` +
`json.dumps(sort_keys=True, default=str)` + SHA256. The `default=str`
defangs UUIDs and datetimes that may appear in command fields.
Non-dataclass commands raise `TypeError` at hash time.

`set` and `frozenset` fields on the command get normalized to sorted
lists before hashing — Python's set iteration order varies across
processes (PYTHONHASHSEED randomizes string hashing) so the same
logical set would produce different `repr` and different hashes
under multiple workers, manifesting as spurious 422 "Idempotency-Key
conflict" responses on legitimate retries. Routes that convert JSON
arrays to `frozenset` for command construction (e.g. permission
sets in `DefinePolicy`) rely on this normalization.

Key length: capped at `_MAX_KEY_LENGTH` (255 chars, matching Stripe's
limit). Longer keys raise `ValueError` from the decorator before any
store lookup or handler invocation.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from typing import Any, Protocol, cast
from uuid import UUID

from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import (
    CachedResult,
    IdempotencyConflictError,
    IdempotencyStore,
)

_MAX_KEY_LENGTH = 255

# structlog loggers are lazy: get_logger() returns a proxy and config
# is applied at first .info() call. Module-level binding is safe even
# though configure_logging() runs later in build_kernel().
_log = get_logger(__name__)


def _normalize_for_hash(obj: Any) -> Any:
    """Recursively normalize containers so the JSON form is hash-stable.

    `set` and `frozenset` are sorted by string form (UUIDs / strings
    both compare lexicographically that way) — without this,
    PYTHONHASHSEED randomizes set iteration across workers and
    breaks idempotency. `dict` and `list`/`tuple` recurse into their
    elements; `tuple` flattens to `list` for JSON. Other primitives
    pass through; non-JSON values still hit `default=str` in the
    `json.dumps` call below.
    """
    # `cast` here because pyright (strict) narrows isinstance(obj, frozenset)
    # to `frozenset[Unknown]` rather than `frozenset[Any]`, even though `obj`
    # is annotated `Any`. The casts assert what asdict() guarantees: nested
    # values are themselves Any-typed.
    if isinstance(obj, (set, frozenset)):
        items_set = cast("set[Any] | frozenset[Any]", obj)
        return sorted((_normalize_for_hash(item) for item in items_set), key=str)
    if isinstance(obj, dict):
        items_dict = cast("dict[Any, Any]", obj)
        return {k: _normalize_for_hash(v) for k, v in items_dict.items()}
    if isinstance(obj, (list, tuple)):
        items_seq = cast("list[Any] | tuple[Any, ...]", obj)
        return [_normalize_for_hash(item) for item in items_seq]
    return obj


def hash_command(command: Any) -> str:
    """SHA256 hex digest of canonical JSON of the command's dict form.

    Raises TypeError if `command` is not a dataclass instance. See the
    module docstring for why set-typed fields are normalized before
    hashing.
    """
    if not is_dataclass(command) or isinstance(command, type):
        msg = (
            f"hash_command requires a dataclass instance, got {type(command).__name__}. "
            "Commands across the codebase are frozen dataclasses by convention."
        )
        raise TypeError(msg)
    normalized = _normalize_for_hash(asdict(command))
    canonical = json.dumps(normalized, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class _BareHandler[TCommand, TResult](Protocol):
    async def __call__(
        self,
        command: TCommand,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
    ) -> TResult: ...


class _IdempotentHandler[TCommand, TResult](Protocol):
    async def __call__(
        self,
        command: TCommand,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
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
        causation_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> TResult:
        if idempotency_key is None:
            return await handler(
                command,
                principal_id=principal_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )

        if len(idempotency_key) > _MAX_KEY_LENGTH:
            msg = f"Idempotency-Key length {len(idempotency_key)} exceeds maximum {_MAX_KEY_LENGTH}"
            raise ValueError(msg)

        cmd_hash = hash_command(command)
        cached = await store.get(principal_id, idempotency_key)
        if cached is not None:
            if cached.command_hash != cmd_hash:
                _log.info(
                    "idempotency.conflict",
                    command_name=command_name,
                    principal_id=str(principal_id),
                    correlation_id=str(correlation_id),
                    key=idempotency_key,
                    expected_hash=cached.command_hash,
                    actual_hash=cmd_hash,
                )
                raise IdempotencyConflictError(
                    key=idempotency_key,
                    expected_hash=cached.command_hash,
                    actual_hash=cmd_hash,
                )
            _log.info(
                "idempotency.cache_hit",
                command_name=command_name,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                key=idempotency_key,
            )
            return deserialize_result(cached.result)

        _log.info(
            "idempotency.cache_miss",
            command_name=command_name,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            key=idempotency_key,
        )
        result = await handler(
            command,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
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
