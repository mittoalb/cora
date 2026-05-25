"""WakeupSource Protocol + two implementations.

The worker calls `await wakeup.wait(timeout_seconds)` between batches
when no new events were processed. The two implementations:

  - `ListenNotifyWakeup`: LISTEN on the `events` channel emitted by the
    AFTER INSERT trigger. Returns immediately on any NOTIFY; latency
    from event commit to projection wake-up is ~tens of ms typical.
    Used when `Settings.projection_use_listen_notify` is True.

  - `PollOnlyWakeup`: just `asyncio.sleep(timeout_seconds)`. No NOTIFY
    dependency. Used when the setting is False — for example, to avoid
    Postgres NOTIFY's global commit `AccessExclusiveLock` under
    contention (per Recall.ai July 2025 incident; trigger documented
    in the NATS deferred-list entry).

Switching between the two is a Settings flip; no projection code
changes. The advance query reads the bookmark and the snapshot horizon
on every batch, so the wake-up signal carries no payload — it's a hint
that "events MIGHT exist," not the events themselves.

Listener connection lifecycle: `ListenNotifyWakeup` holds one
dedicated connection from the pool for the LISTEN. The connection
re-acquires on disconnect (asyncpg raises; the worker's outer retry
loop handles it). One connection out of the pool budget is acceptable
overhead for the latency win.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false

import asyncio
import contextlib
from typing import Any, Protocol

import asyncpg

NOTIFY_CHANNEL = "events"
"""The Postgres NOTIFY channel name set by the AFTER INSERT trigger
(see migration 20260509120000_init_events.sql:38). Constant pulled
out so the listener and the trigger can never drift."""


class WakeupSource(Protocol):
    """Pluggable wake-up signal for the projection worker's idle wait."""

    async def wait(self, timeout_seconds: float) -> None:
        """Block until awakened, or until `timeout_seconds` elapses."""

    async def close(self) -> None:
        """Release any held resources (LISTEN connection, etc.). Safe
        to call multiple times."""


class PollOnlyWakeup:
    """No NOTIFY dependency; just sleeps for the timeout."""

    async def wait(self, timeout_seconds: float) -> None:
        await asyncio.sleep(timeout_seconds)

    async def close(self) -> None:
        return None


class ListenNotifyWakeup:
    """LISTEN on the `events` NOTIFY channel; returns on any notify
    or when the timeout elapses (whichever first).

    Holds one dedicated connection from the pool for the LISTEN. On
    listener disconnect, the next `wait()` re-acquires; the worker's
    outer error handling absorbs the transient failure.

    Lazy connection acquisition: the LISTEN connection is acquired on
    the first `wait()` call, not at construction. This is safe because
    the projection worker uses the advance query (bookmark + xid8
    snapshot horizon) as the source of truth — NOTIFY is purely a
    latency optimization. Events that commit between worker startup
    and first `wait()` are picked up by the next batch advance, not
    by NOTIFY. Once `wait()` runs and acquires the LISTEN connection,
    subsequent commits trigger immediate wake-up.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        # `Any` for the connection because pool.acquire() returns
        # PoolConnectionProxy which pyright won't unify with
        # asyncpg.Connection in this codebase. The proxy delegates
        # to Connection at runtime so the LISTEN/remove_listener
        # interface behaves identically.
        self._conn: Any = None
        self._event = asyncio.Event()
        self._listening = False

    async def _ensure_listening(self) -> None:
        if self._listening and self._conn is not None and not self._conn.is_closed():
            return
        # Acquire (or re-acquire) a dedicated connection and LISTEN.
        if self._conn is not None and self._conn.is_closed():
            self._conn = None
        if self._conn is None:
            self._conn = await self._pool.acquire()
        await self._conn.add_listener(NOTIFY_CHANNEL, self._on_notify)
        self._listening = True

    def _on_notify(
        self,
        _conn: object,
        _pid: int,
        _channel: str,
        _payload: str,
    ) -> None:
        # Wake-up only; payload ignored. Advance query reads bookmark
        # + xid8 snapshot horizon as the source of truth.
        self._event.set()

    async def wait(self, timeout_seconds: float) -> None:
        await self._ensure_listening()
        self._event.clear()
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout_seconds)
        except TimeoutError:
            return  # poll fallback fires; advance loop tries again

    async def close(self) -> None:
        if self._conn is None:
            return
        try:
            if not self._conn.is_closed():
                await self._conn.remove_listener(NOTIFY_CHANNEL, self._on_notify)
        finally:
            # Pool may be closed during shutdown; suppress cleanup errors.
            with contextlib.suppress(asyncpg.InterfaceError, RuntimeError):
                await self._pool.release(self._conn)
            self._conn = None
            self._listening = False


__all__ = ["NOTIFY_CHANNEL", "ListenNotifyWakeup", "PollOnlyWakeup", "WakeupSource"]
