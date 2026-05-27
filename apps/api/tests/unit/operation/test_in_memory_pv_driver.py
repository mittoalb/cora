"""Behavioural tests for `InMemoryPvDriver` + Protocol conformance.

`test_in_memory_pv_driver_satisfies_pv_driver_protocol` is the
runtime conformance check via `@runtime_checkable` `isinstance`;
pyright catches signature drift statically, isinstance catches
method-name drift at runtime. Subsequent production adapters
(Caproto / EpicsCa / EpicsPva) will reuse this pattern.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any, get_args

import pytest

from cora.operation.adapters.in_memory_pv_driver import InMemoryPvDriver
from cora.operation.ports.pv_driver import (
    PvAlarmSeverity,
    PvDriver,
    PvKind,
    PvNotConnectedError,
    PvValue,
)

_FIXED_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)


def _driver() -> InMemoryPvDriver:
    return InMemoryPvDriver(now=lambda: _FIXED_NOW)


@pytest.mark.unit
def test_in_memory_pv_driver_satisfies_pv_driver_protocol() -> None:
    """Runtime `isinstance` check against the `@runtime_checkable` Protocol.

    Catches method-name drift at runtime (pyright catches signature drift
    statically). If `InMemoryPvDriver` renames `get` to `fetch`, this
    fails immediately.
    """
    driver = _driver()
    assert isinstance(driver, PvDriver)


@pytest.mark.unit
async def test_get_on_never_connected_pv_raises_not_connected() -> None:
    driver = _driver()
    with pytest.raises(PvNotConnectedError) as exc_info:
        await driver.get("2bm:rot:rbv")
    assert exc_info.value.pv == "2bm:rot:rbv"


@pytest.mark.unit
async def test_get_after_simulate_disconnect_raises_not_connected() -> None:
    driver = _driver()
    driver.set_value("2bm:rot:rbv", PvValue(kind="scalar", value=1.5, sampled_at=_FIXED_NOW))
    driver.simulate_disconnect("2bm:rot:rbv")
    with pytest.raises(PvNotConnectedError):
        await driver.get("2bm:rot:rbv")


@pytest.mark.unit
async def test_put_on_never_connected_pv_raises_not_connected() -> None:
    driver = _driver()
    with pytest.raises(PvNotConnectedError):
        await driver.put("2bm:rot:val", 3.14)


@pytest.mark.unit
async def test_set_value_makes_pv_observable_via_get() -> None:
    driver = _driver()
    expected = PvValue(kind="scalar", value=2.5, sampled_at=_FIXED_NOW)
    driver.set_value("2bm:rot:rbv", expected)
    actual = await driver.get("2bm:rot:rbv")
    assert actual == expected


@pytest.mark.unit
async def test_put_then_get_round_trips_scalar() -> None:
    driver = _driver()
    driver.simulate_connect("2bm:rot:val")
    await driver.put("2bm:rot:val", 4.2)
    got = await driver.get("2bm:rot:val")
    assert got.kind == "scalar"
    assert got.value == 4.2
    assert got.sampled_at == _FIXED_NOW


@pytest.mark.unit
async def test_put_then_get_round_trips_array_as_tuple() -> None:
    driver = _driver()
    driver.simulate_connect("2bm:cam:image")
    await driver.put("2bm:cam:image", (1, 2, 3, 4))
    got = await driver.get("2bm:cam:image")
    assert got.kind == "array"
    assert got.value == (1, 2, 3, 4)


@pytest.mark.unit
async def test_put_ignores_wait_and_timeout_kwargs() -> None:
    """In-memory has no IOC callback; the kwargs are accepted but inert."""
    driver = _driver()
    driver.simulate_connect("2bm:rot:val")
    await driver.put("2bm:rot:val", 1.0, wait=False, timeout_s=0.001)
    assert (await driver.get("2bm:rot:val")).value == 1.0


@pytest.mark.unit
async def test_subscribe_yields_values_pushed_after_subscription() -> None:
    driver = _driver()
    driver.set_value("2bm:rot:rbv", PvValue(kind="scalar", value=0.0, sampled_at=_FIXED_NOW))
    iterator = await driver.subscribe("2bm:rot:rbv")
    driver.set_value("2bm:rot:rbv", PvValue(kind="scalar", value=1.0, sampled_at=_FIXED_NOW))
    driver.set_value("2bm:rot:rbv", PvValue(kind="scalar", value=2.0, sampled_at=_FIXED_NOW))

    received = [(await anext(iterator)).value, (await anext(iterator)).value]
    assert received == [1.0, 2.0]
    await iterator.aclose()


@pytest.mark.unit
async def test_subscribe_raises_not_connected_on_simulated_disconnect() -> None:
    driver = _driver()
    driver.set_value("2bm:rot:rbv", PvValue(kind="scalar", value=0.0, sampled_at=_FIXED_NOW))
    iterator = await driver.subscribe("2bm:rot:rbv")
    driver.simulate_disconnect("2bm:rot:rbv")
    with pytest.raises(PvNotConnectedError) as exc_info:
        await anext(iterator)
    assert exc_info.value.pv == "2bm:rot:rbv"


@pytest.mark.unit
async def test_subscribe_on_never_connected_pv_raises_not_connected() -> None:
    driver = _driver()
    with pytest.raises(PvNotConnectedError):
        await driver.subscribe("2bm:rot:rbv")


@pytest.mark.unit
async def test_subscribe_isolated_between_pvs() -> None:
    driver = _driver()
    driver.set_value("2bm:rot:rbv", PvValue(kind="scalar", value=0.0, sampled_at=_FIXED_NOW))
    driver.set_value("2bm:cam:frame", PvValue(kind="scalar", value=0.0, sampled_at=_FIXED_NOW))
    rot_iter = await driver.subscribe("2bm:rot:rbv")
    driver.set_value("2bm:cam:frame", PvValue(kind="scalar", value=99.0, sampled_at=_FIXED_NOW))
    driver.set_value("2bm:rot:rbv", PvValue(kind="scalar", value=1.0, sampled_at=_FIXED_NOW))
    got = await anext(rot_iter)
    assert got.value == 1.0
    await rot_iter.aclose()


@pytest.mark.unit
async def test_subscribe_fans_out_to_multiple_subscribers() -> None:
    driver = _driver()
    driver.set_value("2bm:rot:rbv", PvValue(kind="scalar", value=0.0, sampled_at=_FIXED_NOW))
    iter_a = await driver.subscribe("2bm:rot:rbv")
    iter_b = await driver.subscribe("2bm:rot:rbv")
    driver.set_value("2bm:rot:rbv", PvValue(kind="scalar", value=7.0, sampled_at=_FIXED_NOW))
    assert (await anext(iter_a)).value == 7.0
    assert (await anext(iter_b)).value == 7.0
    await iter_a.aclose()
    await iter_b.aclose()


@pytest.mark.unit
async def test_subscribe_yields_put_values_to_active_subscribers() -> None:
    driver = _driver()
    driver.simulate_connect("2bm:rot:val")
    iterator = await driver.subscribe("2bm:rot:val")
    await driver.put("2bm:rot:val", 9.5)
    got = await anext(iterator)
    assert got.value == 9.5
    assert got.kind == "scalar"
    await iterator.aclose()


@pytest.mark.unit
async def test_subscribe_cleanup_removes_queue_after_iteration_and_close() -> None:
    """Closing a consumed iterator drops its queue from the subscriber list.

    Async generators run their `finally` block only after the generator has
    been started; this test reflects realistic usage (subscribe, consume,
    close) where the cleanup pathway actually runs.
    """
    driver = _driver()
    driver.set_value("2bm:rot:rbv", PvValue(kind="scalar", value=0.0, sampled_at=_FIXED_NOW))
    iterator = await driver.subscribe("2bm:rot:rbv")
    assert len(driver._subscribers["2bm:rot:rbv"]) == 1  # pyright: ignore[reportPrivateUsage]
    driver.set_value("2bm:rot:rbv", PvValue(kind="scalar", value=1.0, sampled_at=_FIXED_NOW))
    await anext(iterator)
    await iterator.aclose()
    assert driver._subscribers["2bm:rot:rbv"] == []  # pyright: ignore[reportPrivateUsage]


@pytest.mark.unit
async def test_consumer_cancellation_removes_subscriber_queue() -> None:
    """Cancellation mid-`anext` runs the generator's `finally` and unregisters.

    Pins the cancellation-safety invariant the production adapters at
    Stage-1b through Stage-1d must preserve.
    """
    driver = _driver()
    driver.set_value("2bm:rot:rbv", PvValue(kind="scalar", value=0.0, sampled_at=_FIXED_NOW))
    iterator = await driver.subscribe("2bm:rot:rbv")
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(anext(iterator), timeout=0.05)
    assert driver._subscribers["2bm:rot:rbv"] == []  # pyright: ignore[reportPrivateUsage]


@pytest.mark.unit
async def test_simulate_disconnect_drops_cached_value() -> None:
    """Reconnect after disconnect must not observe pre-disconnect cached value.

    Mirrors real CA/PVA semantics: disconnect invalidates the cached
    value; the operator must re-fetch from the IOC.
    """
    driver = _driver()
    driver.set_value("2bm:rot:rbv", PvValue(kind="scalar", value=1.5, sampled_at=_FIXED_NOW))
    driver.simulate_disconnect("2bm:rot:rbv")
    driver.simulate_connect("2bm:rot:rbv")
    with pytest.raises(PvNotConnectedError):
        await driver.get("2bm:rot:rbv")


@pytest.mark.unit
async def test_put_default_now_yields_utc_aware_sampled_at() -> None:
    """Default `now=None` path produces a tz-aware UTC datetime.

    Pins the contract the production adapters inherit; tz-naive
    `sampled_at` would silently break downstream PROV-O time fields.
    """
    driver = InMemoryPvDriver()
    driver.simulate_connect("2bm:rot:val")
    await driver.put("2bm:rot:val", 1.0)
    got = await driver.get("2bm:rot:val")
    assert got.sampled_at.tzinfo is UTC


@pytest.mark.unit
@pytest.mark.parametrize("kind", get_args(PvKind))
def test_pv_value_accepts_every_pv_kind_literal(kind: str) -> None:
    """Pins the closed `PvKind` set; an accidental narrowing fails fast."""
    value: Any = (1, 2) if kind == "array" else ("label" if kind == "enum" else 0)
    pv_value = PvValue(kind=kind, value=value, sampled_at=_FIXED_NOW)  # type: ignore[arg-type]
    assert pv_value.kind == kind


@pytest.mark.unit
@pytest.mark.parametrize("severity", get_args(PvAlarmSeverity))
def test_pv_value_accepts_every_alarm_severity_literal(severity: str) -> None:
    """Pins the closed `PvAlarmSeverity` set against accidental narrowing."""
    pv_value = PvValue(
        kind="scalar",
        value=1.0,
        sampled_at=_FIXED_NOW,
        alarm_severity=severity,  # type: ignore[arg-type]
    )
    assert pv_value.alarm_severity == severity
