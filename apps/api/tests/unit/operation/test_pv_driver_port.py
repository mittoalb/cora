"""Port-surface tests for `PvDriver`: PvValue immutability + exception attrs.

Locks the surface promises the production adapters (CaprotoPvDriver,
EpicsCaPvDriver, EpicsPvaPvDriver) will inherit at Stage-1b through
Stage-1d. Behavioural tests for `InMemoryPvDriver` live in
`test_in_memory_pv_driver.py`.
"""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from cora.operation.ports.pv_driver import (
    NoAdapterForPvError,
    PvAccessDeniedError,
    PvNotConnectedError,
    PvPutFailedError,
    PvTimeoutError,
    PvTypeCoercionError,
    PvValue,
)


@pytest.mark.unit
def test_pv_value_is_frozen_dataclass() -> None:
    v = PvValue(kind="scalar", value=1.5, sampled_at=datetime(2026, 5, 27, tzinfo=UTC))
    with pytest.raises(FrozenInstanceError):
        v.value = 2.0  # type: ignore[misc]


@pytest.mark.unit
def test_pv_value_defaults_alarm_severity_to_none() -> None:
    v = PvValue(kind="scalar", value=1.5, sampled_at=datetime(2026, 5, 27, tzinfo=UTC))
    assert v.alarm_severity == "NONE"
    assert v.alarm_status == ""


@pytest.mark.unit
def test_pv_value_equality_by_field_tuple() -> None:
    ts = datetime(2026, 5, 27, tzinfo=UTC)
    a = PvValue(kind="scalar", value=1.5, sampled_at=ts)
    b = PvValue(kind="scalar", value=1.5, sampled_at=ts)
    assert a == b
    assert hash(a) == hash(b)


@pytest.mark.unit
def test_pv_not_connected_error_carries_pv_name() -> None:
    err = PvNotConnectedError("2bm:rot:rbv")
    assert err.pv == "2bm:rot:rbv"
    assert "2bm:rot:rbv" in str(err)


@pytest.mark.unit
def test_pv_timeout_error_carries_pv_and_timeout() -> None:
    err = PvTimeoutError("2bm:rot:val", timeout_s=5.0)
    assert err.pv == "2bm:rot:val"
    assert err.timeout_s == 5.0
    assert "5.0" in str(err)


@pytest.mark.unit
def test_pv_put_failed_error_carries_pv_and_reason() -> None:
    err = PvPutFailedError("2bm:rot:val", reason="read-only")
    assert err.pv == "2bm:rot:val"
    assert err.reason == "read-only"
    assert "read-only" in str(err)


@pytest.mark.unit
def test_pv_type_coercion_error_carries_pv_raw_type_and_target_kind() -> None:
    err = PvTypeCoercionError("2bm:cam:image", raw_type="NTFancy", target_kind="array")
    assert err.pv == "2bm:cam:image"
    assert err.raw_type == "NTFancy"
    assert err.target_kind == "array"


@pytest.mark.unit
def test_pv_access_denied_error_carries_pv() -> None:
    err = PvAccessDeniedError("2bm:safety:shutter")
    assert err.pv == "2bm:safety:shutter"


@pytest.mark.unit
def test_no_adapter_for_pv_error_carries_pv() -> None:
    err = NoAdapterForPvError("unrouted:something")
    assert err.pv == "unrouted:something"
