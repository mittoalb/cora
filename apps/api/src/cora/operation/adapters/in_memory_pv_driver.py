"""In-memory `PvDriver` adapter for unit tests and `app_env=test`.

Mirrors `cora.infrastructure.adapters.in_memory_event_store` and
`cora.infrastructure.adapters.in_memory_profile_store`: dict-backed,
no sockets, no real IOC. Tests inject values via `set_value` /
`simulate_disconnect` / `simulate_connect`; production code paths
call `get` / `put` / `subscribe` against the same instance and
observe the injected state.

Per [[project_test_infra]]'s 5-tier pyramid, this adapter serves the
unit tier. Per [[project_control_port_design]] P0 gate-review
resolution it is required before any production adapter ships, so
that Operation BC executor tests stay 100% in-process without
caproto / aioca / p4p dependencies.

## Connection model

A PV is "connected" iff `set_value` or `simulate_connect` has been
called for it. `get` and `put` against a PV that is not connected
raise `PvNotConnectedError`. `simulate_disconnect` marks a connected
PV as disconnected and pushes a sentinel to every active subscriber
so the subscribe iterator raises `PvNotConnectedError` mid-stream
(matching the production p4p `notify_disconnect=True` semantic
documented in [[project_control_port_design]]).

## put semantics

`put` accepts the same primitive value set as the production
adapters (`int | float | bool | str | tuple[Any, ...]`) and
constructs a `PvValue` for the store: tuples become `kind="array"`,
all other primitives become `kind="scalar"`. `sampled_at` is read
from the injectable `now` callable (defaults to
`lambda: datetime.now(tz=UTC)`); `alarm_severity` stays `"NONE"`,
`alarm_status` stays `""`. Tests that need a specific kind or
alarm shape use `set_value` to push an explicit `PvValue`.

`wait` and `timeout_s` are accepted to satisfy the Protocol but
ignored: in-memory has no IOC round-trip, so caput-callback /
timeout semantics do not apply. The contract is preserved at the
type level, mirroring how `InMemoryProfileStore.scrub_and_delete`
accepts and ignores the asyncpg `conn` parameter.

## Subscribe semantics

`subscribe` returns an async iterator that yields each `PvValue`
pushed to the PV after the subscription is established. Each
subscriber gets its own queue; pushing to a PV fans out to every
subscriber's queue (no coalescing in this adapter, matching the
"each test controls its own ID space" discipline). The iterator
cleans up its queue on `aclose()` or on
`PvNotConnectedError` propagation.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from cora.operation.ports.pv_driver import (
    PvKind,
    PvNotConnectedError,
    PvValue,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable


class _DisconnectSentinel:
    """Marker pushed to subscriber queues on `simulate_disconnect`.

    Kept as a private class (not a singleton instance) so that
    `isinstance` checks in the drain loop stay unambiguous and the
    sentinel cannot collide with any legitimate `PvValue` consumer
    might push through a future extension.
    """


_DISCONNECT = _DisconnectSentinel()
"""Module-level singleton of the disconnect marker."""


class InMemoryPvDriver:
    """Process-local dict adapter for `PvDriver`.

    See module docstring for the connection model, put semantics, and
    subscribe semantics. Per-PV state is kept in three dicts so that
    PV name collisions across kinds raise type errors loudly rather
    than silently overlap.
    """

    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._values: dict[str, PvValue] = {}
        self._connected: set[str] = set()
        self._subscribers: dict[str, list[asyncio.Queue[PvValue | _DisconnectSentinel]]] = {}
        self._now: Callable[[], datetime] = now or (lambda: datetime.now(tz=UTC))

    def set_value(self, pv: str, value: PvValue) -> None:
        """Install `value` as the current value of `pv` and fan out to subscribers.

        Marks the PV as connected if it was not already. Test entry
        point for seeding state before exercising production code
        paths.
        """
        self._values[pv] = value
        self._connected.add(pv)
        for queue in self._subscribers.get(pv, []):
            queue.put_nowait(value)

    def simulate_connect(self, pv: str) -> None:
        """Mark `pv` as connected without installing a value.

        Useful for tests that want `put` to succeed (and the resulting
        value to be observable via `get`) without pre-seeding a
        `set_value` call.
        """
        self._connected.add(pv)

    def simulate_disconnect(self, pv: str) -> None:
        """Mark `pv` as disconnected, drop its cached value, and signal subscribers.

        Subsequent `get` / `put` raise `PvNotConnectedError`. Each
        active subscriber's iterator raises `PvNotConnectedError`
        through the `async for` (matching the production
        p4p notify-disconnect semantic).

        Cached value is cleared so a reconnect-then-get does not
        observe stale data; matches real CA/PVA semantics where
        disconnect invalidates the cached value (operator must
        re-fetch).
        """
        self._connected.discard(pv)
        self._values.pop(pv, None)
        for queue in self._subscribers.get(pv, []):
            queue.put_nowait(_DISCONNECT)

    async def get(self, pv: str) -> PvValue:
        if pv not in self._connected:
            raise PvNotConnectedError(pv)
        cached = self._values.get(pv)
        if cached is None:
            raise PvNotConnectedError(pv)
        return cached

    async def put(
        self,
        pv: str,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        _ = (wait, timeout_s)
        if pv not in self._connected:
            raise PvNotConnectedError(pv)
        kind: PvKind = "array" if isinstance(value, tuple) else "scalar"
        pv_value = PvValue(kind=kind, value=value, sampled_at=self._now())
        self._values[pv] = pv_value
        for queue in self._subscribers.get(pv, []):
            queue.put_nowait(pv_value)

    async def subscribe(self, pv: str) -> AsyncGenerator[PvValue]:
        """Return type narrows the Protocol's `AsyncIterator` to `AsyncGenerator`.

        Covariant return type lets tests close subscriptions via the
        iterator's `aclose()` while production callers still see the
        `AsyncIterator` contract through the Protocol surface.
        """
        if pv not in self._connected:
            raise PvNotConnectedError(pv)
        queue: asyncio.Queue[PvValue | _DisconnectSentinel] = asyncio.Queue()
        self._subscribers.setdefault(pv, []).append(queue)
        return self._drain(pv, queue)

    async def _drain(
        self,
        pv: str,
        queue: asyncio.Queue[PvValue | _DisconnectSentinel],
    ) -> AsyncGenerator[PvValue]:
        try:
            while True:
                item = await queue.get()
                if isinstance(item, _DisconnectSentinel):
                    raise PvNotConnectedError(pv)
                yield item
        finally:
            subs = self._subscribers.get(pv)
            if subs is not None and queue in subs:
                subs.remove(queue)


__all__ = ["InMemoryPvDriver"]
