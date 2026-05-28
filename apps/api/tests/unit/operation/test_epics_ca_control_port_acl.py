"""Unit-tier ACL tests for `EpicsCaControlPort` error mapping.

Per [[project_control_port_test_isolation_research]] watch item 4:
the `pv.read` / `pv.write` timeout + IOC-rejection ACL arms can't be
exercised against the softIOC fixture (no native slow-getter or
write-reject record). This file covers those branches with monkey-
patched aioca functions raising `CANothing` with the relevant
`ECA_*` errorcodes; the adapter's `_map_ca_error` translation is
pinned end-to-end.

Coverage:

  - `ECA_TIMEOUT` on read -> `ControlTimeoutError(address, timeout_s)`
  - `ECA_TIMEOUT` on write -> `ControlTimeoutError(address, timeout_s)`
  - `ECA_DISCONN` on cainfo -> `ControlNotConnectedError(address)`
  - non-success errorcode on write -> `ControlWriteRejectedError`
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false

from typing import Any

import pytest
from aioca import CANothing
from epicscorelibs.ca import cadef

from cora.operation.adapters.epics_ca_control_port import EpicsCaControlPort
from cora.operation.ports.control_port import (
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlWriteRejectedError,
)


class _FakeCAInfo:
    """Stand-in `CAInfo` reporting connected state."""

    OPEN = 2

    def __init__(self, *, state: int = cadef.cs_conn) -> None:
        self.state = state


async def _ok_cainfo(_address: str) -> _FakeCAInfo:
    return _FakeCAInfo()


async def _raise_disconn(*_args: Any, **_kwargs: Any) -> None:
    raise CANothing("test_pv", cadef.ECA_DISCONN)


async def _raise_timeout(*_args: Any, **_kwargs: Any) -> None:
    raise CANothing("test_pv", cadef.ECA_TIMEOUT)


async def _raise_other_errorcode(*_args: Any, **_kwargs: Any) -> None:
    raise CANothing("test_pv", 999)


@pytest.mark.unit
async def test_read_translates_eca_timeout_to_control_timeout_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`CANothing(ECA_TIMEOUT)` on caget surfaces as `ControlTimeoutError`."""
    monkeypatch.setattr("cora.operation.adapters.epics_ca_control_port.cainfo", _ok_cainfo)
    monkeypatch.setattr("cora.operation.adapters.epics_ca_control_port.caget", _raise_timeout)
    port = EpicsCaControlPort(default_timeout_s=0.5)
    with pytest.raises(ControlTimeoutError) as exc_info:
        await port.read("test_pv")
    assert exc_info.value.address == "test_pv"
    assert exc_info.value.timeout_s == 0.5


@pytest.mark.unit
async def test_write_translates_eca_timeout_to_control_timeout_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`CANothing(ECA_TIMEOUT)` on caput surfaces as `ControlTimeoutError`."""
    monkeypatch.setattr("cora.operation.adapters.epics_ca_control_port.cainfo", _ok_cainfo)
    monkeypatch.setattr("cora.operation.adapters.epics_ca_control_port.caput", _raise_timeout)
    port = EpicsCaControlPort()
    with pytest.raises(ControlTimeoutError) as exc_info:
        await port.write("test_pv", 1.0, timeout_s=2.5)
    assert exc_info.value.address == "test_pv"
    assert exc_info.value.timeout_s == 2.5


@pytest.mark.unit
async def test_cainfo_eca_disconn_translates_to_not_connected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `CANothing(ECA_DISCONN)` at the connection precondition becomes NotConnected."""
    monkeypatch.setattr("cora.operation.adapters.epics_ca_control_port.cainfo", _raise_disconn)
    port = EpicsCaControlPort()
    with pytest.raises(ControlNotConnectedError) as exc_info:
        await port.read("test_pv")
    assert exc_info.value.address == "test_pv"


@pytest.mark.unit
async def test_write_translates_other_errorcode_to_write_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-TIMEOUT non-DISCONN `CANothing` on caput becomes `ControlWriteRejectedError`."""
    monkeypatch.setattr("cora.operation.adapters.epics_ca_control_port.cainfo", _ok_cainfo)
    monkeypatch.setattr(
        "cora.operation.adapters.epics_ca_control_port.caput", _raise_other_errorcode
    )
    port = EpicsCaControlPort()
    with pytest.raises(ControlWriteRejectedError) as exc_info:
        await port.write("test_pv", 1.0)
    assert exc_info.value.address == "test_pv"
    assert "999" in exc_info.value.reason
