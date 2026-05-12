"""Unit tests for PollOnlyWakeup. ListenNotifyWakeup is exercised in
the integration suite (needs a real Postgres LISTEN connection)."""

import asyncio

import pytest

from cora.infrastructure.projection.wakeup import PollOnlyWakeup


@pytest.mark.unit
async def test_poll_only_wakeup_sleeps_for_timeout() -> None:
    wakeup = PollOnlyWakeup()
    loop = asyncio.get_event_loop()

    start = loop.time()
    await wakeup.wait(0.15)
    elapsed = loop.time() - start

    # Allow generous slack for CI variance; the floor matters more
    # than the ceiling.
    assert 0.10 <= elapsed <= 0.50


@pytest.mark.unit
async def test_poll_only_wakeup_close_is_safe_to_call_repeatedly() -> None:
    wakeup = PollOnlyWakeup()
    await wakeup.close()
    await wakeup.close()  # idempotent


@pytest.mark.unit
async def test_poll_only_wakeup_responds_to_cancellation() -> None:
    """The worker cancels the wait task on shutdown; PollOnlyWakeup
    must propagate cancellation cleanly."""
    wakeup = PollOnlyWakeup()
    task = asyncio.create_task(wakeup.wait(60.0))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
