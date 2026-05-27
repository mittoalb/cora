"""Integration tests: `CaprotoControlPort` against an in-process caproto IOC.

Stage-1b of the control-port arc per [[project_control_port_design]]
+ [[project_control_port_generalization_research]]. Exercises the
ACL translation (caproto `ReadNotifyResponse` -> CORA `Reading`)
end-to-end across every `ReadingKind` branch the test IOC exposes
(Scalar, Array, Categorical) plus the error paths
(`ControlNotConnectedError`, `ControlTimeoutError`,
`ControlWriteRejectedError`) and the `Quality` ACL (Good + Bad).

The `caproto_ioc` fixture (see `tests/integration/conftest.py`)
spins up a per-test IOC on an ephemeral loopback port; the adapter's
lazy `Context()` picks up the fixture's monkeypatched env vars on
first call. xdist-safe under `-n 4`.

Image / Tabular kinds + non-Good non-Bad quality (Uncertain) are
out of scope here: CA does not natively carry NTNDArray (PVA does);
CORA has no NTTable consumer yet; the IOC has no convenient way to
trigger MINOR alarm without value-driven thresholds. Those branches
land with the PVA / future substrate adapters.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import asyncio

import pytest

from cora.operation.adapters.caproto_control_port import CaprotoControlPort
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    ControlPort,
    ControlTimeoutError,
    Reading,
)


@pytest.mark.integration
def test_caproto_control_port_satisfies_control_port_protocol() -> None:
    """Runtime `isinstance` check against the `@runtime_checkable` Protocol.

    Production adapters at Stage-1c (`EpicsCaControlPort` via aioca)
    and Stage-1d (`EpicsPvaControlPort` via p4p) MUST reuse this
    pattern. Catches method-name drift at runtime; needs no IOC.
    """
    assert isinstance(CaprotoControlPort(), ControlPort)


@pytest.mark.integration
async def test_read_double_scalar_returns_reading_with_good_quality(
    caproto_ioc: str,
) -> None:
    """DBR_DOUBLE scalar lands as Reading(kind='Scalar', quality='Good', value=float)."""
    port = CaprotoControlPort()
    try:
        reading = await port.read(f"{caproto_ioc}double_value")
        assert isinstance(reading, Reading)
        assert reading.kind == "Scalar"
        assert reading.quality == "Good"
        assert reading.value == 0.0
        assert reading.sampled_at.tzinfo is not None
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_long_scalar_returns_int_value(caproto_ioc: str) -> None:
    """DBR_LONG scalar lands as Reading(kind='Scalar', value=int)."""
    port = CaprotoControlPort()
    try:
        reading = await port.read(f"{caproto_ioc}long_value")
        assert reading.kind == "Scalar"
        assert reading.value == 0
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_string_scalar_returns_decoded_utf8(caproto_ioc: str) -> None:
    """DBR_STRING scalar lands decoded as Python `str`, not raw `bytes`."""
    port = CaprotoControlPort()
    try:
        reading = await port.read(f"{caproto_ioc}string_value")
        assert reading.kind == "Scalar"
        assert reading.value == "initial"
        assert isinstance(reading.value, str)
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_waveform_returns_array_as_tuple(caproto_ioc: str) -> None:
    """DBR_DOUBLE count > 1 lands as Reading(kind='Array', value=tuple)."""
    port = CaprotoControlPort()
    try:
        reading = await port.read(f"{caproto_ioc}waveform")
        assert reading.kind == "Array"
        assert isinstance(reading.value, tuple)
        assert reading.value == (0.0, 0.0, 0.0, 0.0)
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_enum_returns_categorical_kind(caproto_ioc: str) -> None:
    """DBR_ENUM lands as Reading(kind='Categorical') regardless of count."""
    port = CaprotoControlPort()
    try:
        reading = await port.read(f"{caproto_ioc}enum_value")
        assert reading.kind == "Categorical"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_major_alarm_pv_returns_bad_quality(caproto_ioc: str) -> None:
    """MAJOR_ALARM severity from the IOC translates to Quality='Bad' with quality_detail."""
    port = CaprotoControlPort()
    try:
        reading = await port.read(f"{caproto_ioc}bad_quality_value")
        assert reading.quality == "Bad"
        assert reading.value == 99.9
        assert reading.quality_detail != ""
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_slow_pv_with_short_timeout_raises_control_timeout(
    caproto_ioc: str,
) -> None:
    """Slow IOC getter triggers ControlTimeoutError on the read path.

    Pins the `pv.read` timeout -> `ControlTimeoutError` ACL arm
    (distinct from the `wait_for_connection` -> `ControlNotConnectedError`
    arm exercised by the nonexistent-PV tests).
    """
    port = CaprotoControlPort(default_timeout_s=0.1)
    try:
        with pytest.raises(ControlTimeoutError) as exc_info:
            await port.read(f"{caproto_ioc}slow_value")
        assert exc_info.value.address == f"{caproto_ioc}slow_value"
        assert exc_info.value.timeout_s == 0.1
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_scalar_then_read_observes_new_value(caproto_ioc: str) -> None:
    """caput-callback semantics: after `wait=True` write returns, read sees new value."""
    port = CaprotoControlPort()
    try:
        await port.write(f"{caproto_ioc}double_value", 4.2, wait=True)
        reading = await port.read(f"{caproto_ioc}double_value")
        assert reading.value == 4.2
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_long_then_read_observes_new_value(caproto_ioc: str) -> None:
    """DBR_LONG write round-trip pin: integer survives caput-callback + read."""
    port = CaprotoControlPort()
    try:
        await port.write(f"{caproto_ioc}long_value", 99, wait=True)
        reading = await port.read(f"{caproto_ioc}long_value")
        assert reading.value == 99
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_subscribe_yields_initial_value_then_writes(caproto_ioc: str) -> None:
    """Subscribe gets the current value first, then each write fans out as a Reading."""
    port = CaprotoControlPort()
    try:
        iterator = await port.subscribe(f"{caproto_ioc}double_value")
        first = await asyncio.wait_for(anext(iterator), timeout=2.0)
        assert first.value == 0.0

        await port.write(f"{caproto_ioc}double_value", 7.7, wait=True)
        second = await asyncio.wait_for(anext(iterator), timeout=2.0)
        assert second.value == 7.7

        await iterator.aclose()
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_subscribe_cancellation_runs_generator_finally(caproto_ioc: str) -> None:
    """Consumer cancellation mid-`anext` runs the drain generator's finally + sub.clear.

    Mirrors `test_consumer_cancellation_removes_subscriber_queue` for
    the in-memory port. Pins the cancellation-safety invariant that
    Stage-1c / Stage-1d production adapters must preserve.
    """
    port = CaprotoControlPort()
    try:
        iterator = await port.subscribe(f"{caproto_ioc}double_value")
        await asyncio.wait_for(anext(iterator), timeout=2.0)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(anext(iterator), timeout=0.05)
        await iterator.aclose()
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_read_on_nonexistent_pv_raises_not_connected(caproto_ioc: str) -> None:
    """A PV no IOC serves never connects; short timeout becomes ControlNotConnectedError."""
    port = CaprotoControlPort(default_timeout_s=0.3)
    try:
        with pytest.raises(ControlNotConnectedError) as exc_info:
            await port.read(f"{caproto_ioc}nonexistent")
        assert exc_info.value.address == f"{caproto_ioc}nonexistent"
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_write_on_nonexistent_pv_raises_not_connected(caproto_ioc: str) -> None:
    """Write path mirrors the read path: never-connect surfaces as ControlNotConnectedError."""
    port = CaprotoControlPort(default_timeout_s=0.3)
    try:
        with pytest.raises(ControlNotConnectedError):
            await port.write(f"{caproto_ioc}nonexistent", 1.0)
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_subscribe_on_nonexistent_pv_raises_not_connected(caproto_ioc: str) -> None:
    """Subscribe path mirrors the read path: never-connect surfaces as ControlNotConnectedError."""
    port = CaprotoControlPort(default_timeout_s=0.3)
    try:
        with pytest.raises(ControlNotConnectedError):
            await port.subscribe(f"{caproto_ioc}nonexistent")
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_pv_cache_reuses_resolved_pv(caproto_ioc: str) -> None:
    """Repeat reads against the same address reuse the cached PV object."""
    port = CaprotoControlPort()
    try:
        await port.read(f"{caproto_ioc}double_value")
        cached_id = id(port._pvs[f"{caproto_ioc}double_value"])  # pyright: ignore[reportPrivateUsage]
        await port.read(f"{caproto_ioc}double_value")
        assert id(port._pvs[f"{caproto_ioc}double_value"]) == cached_id  # pyright: ignore[reportPrivateUsage]
    finally:
        await port.aclose()


@pytest.mark.integration
async def test_aclose_is_idempotent(caproto_ioc: str) -> None:
    """Second aclose() call is a no-op (matches the InMemoryControlPort lifecycle)."""
    port = CaprotoControlPort()
    await port.read(f"{caproto_ioc}double_value")
    await port.aclose()
    await port.aclose()
    assert port._context is None  # pyright: ignore[reportPrivateUsage]
