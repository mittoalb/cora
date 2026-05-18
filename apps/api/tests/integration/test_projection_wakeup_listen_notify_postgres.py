"""Integration tests for `ListenNotifyWakeup` against real Postgres.

This is the production wake-up source — `Settings.projection_use_listen_notify`
defaults to True, so every deploy without an explicit override runs on
this implementation. `PollOnlyWakeup` is covered by unit tests in
`tests/unit/projection/test_wakeup.py`.

Pins each reachable behavioral edge:
  - wait() returns immediately on pg_notify (latency well below timeout)
  - wait() returns on timeout when no NOTIFY arrives
  - close() before any wait() is a no-op (lazy acquisition)
  - close() is idempotent
  - second wait() reuses the same listener connection (early-return path)

The `is_closed() == True` branches in `_ensure_listening` (line 97) and
`close` (line 127) are unreachable under asyncpg's `PoolConnectionProxy`
semantics: when the underlying backend dies, the pool auto-releases the
proxy, and `is_closed()` then raises `InterfaceError` rather than
returning True. The outer worker retry loop is what actually recovers
from listener disconnects — see [[project_phase_plan]] for the
defer/clean-up follow-up.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false

import asyncio

import asyncpg
import pytest

from cora.infrastructure.projection.wakeup import NOTIFY_CHANNEL, ListenNotifyWakeup


async def _send_notify(pool: asyncpg.Pool, payload: str = "test") -> None:
    """Fire a NOTIFY on the events channel from a non-listener connection.

    asyncpg's `execute` runs in autocommit when not inside a `.transaction()`
    block, so NOTIFY is delivered at the implicit COMMIT immediately after.
    """
    async with pool.acquire() as conn:
        await conn.execute(f"NOTIFY {NOTIFY_CHANNEL}, '{payload}'")


@pytest.mark.integration
async def test_wait_returns_immediately_on_notify(db_pool: asyncpg.Pool) -> None:
    wakeup = ListenNotifyWakeup(db_pool)
    loop = asyncio.get_event_loop()
    try:
        wait_task = asyncio.create_task(wakeup.wait(5.0))
        # Yield once so the listener is registered before we NOTIFY,
        # otherwise the notification can arrive before add_listener and
        # be dropped. The wait() coroutine awaits _ensure_listening
        # first, so a single sleep(0) lets it run to the add_listener
        # call.
        await asyncio.sleep(0.05)

        start = loop.time()
        await _send_notify(db_pool, "wakeup-test")
        await asyncio.wait_for(wait_task, timeout=2.0)
        elapsed = loop.time() - start

        # NOTIFY delivery is typically tens of ms; well below the 5s
        # timeout we passed to wait(). Generous slack for CI variance.
        assert elapsed < 1.0
    finally:
        await wakeup.close()


@pytest.mark.integration
async def test_wait_returns_on_timeout_when_no_notify(db_pool: asyncpg.Pool) -> None:
    wakeup = ListenNotifyWakeup(db_pool)
    loop = asyncio.get_event_loop()
    try:
        start = loop.time()
        await wakeup.wait(0.15)
        elapsed = loop.time() - start
        assert 0.10 <= elapsed <= 0.60
    finally:
        await wakeup.close()


@pytest.mark.integration
async def test_close_before_first_wait_is_safe(db_pool: asyncpg.Pool) -> None:
    """Lazy acquisition: no connection is held until the first wait()."""
    wakeup = ListenNotifyWakeup(db_pool)
    await wakeup.close()
    assert wakeup._conn is None


@pytest.mark.integration
async def test_close_is_idempotent(db_pool: asyncpg.Pool) -> None:
    wakeup = ListenNotifyWakeup(db_pool)
    try:
        await wakeup.wait(0.05)
    finally:
        await wakeup.close()
        await wakeup.close()  # second call hits the conn-is-None early return


@pytest.mark.integration
async def test_second_wait_reuses_listener_connection(db_pool: asyncpg.Pool) -> None:
    """The already-listening fast path skips re-acquisition.

    Pins the `_listening and conn and not is_closed -> return` short-
    circuit at the top of `_ensure_listening`. Without it the listener
    would re-register on every wait, leaking connections under the
    worker's normal busy-loop.
    """
    wakeup = ListenNotifyWakeup(db_pool)
    try:
        await wakeup.wait(0.05)
        conn_after_first = wakeup._conn
        assert conn_after_first is not None

        await wakeup.wait(0.05)
        assert wakeup._conn is conn_after_first  # same proxy instance
    finally:
        await wakeup.close()
