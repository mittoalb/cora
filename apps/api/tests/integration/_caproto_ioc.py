"""Minimal in-process caproto IOC for integration-tier `ControlPort` tests.

Per [[project_control_port_design]] § Test surface and the Stage-1b
plan in [[project_control_port_generalization_research]], CORA uses
caproto for the integration tier ONLY: caproto runs both an
in-process Python IOC AND the asyncio CA client that talks to it,
inside the same pytest process. This avoids testcontainers / softIOC
binaries / EPICS Base system installation while still exercising the
real CA wire protocol end-to-end.

The maintainers' own README warns against caproto in production
(two-maintainer hybrid project, "applications requiring battle-tested
reliability should steer well clear"). Stage-1c+1d ship production
adapters via aioca + p4p.

## IOC shape

`CoraTestIOC` exposes a small but representative PV menu so the
integration tests can cover every `ReadingKind` branch the
`CaprotoControlPort` adapter must translate plus the Quality + timeout
error arms:

  - `double_value` (DBR_DOUBLE scalar)         -> `Reading(kind="Scalar")`
  - `long_value`   (DBR_LONG   scalar)         -> `Reading(kind="Scalar")`
  - `string_value` (DBR_STRING scalar)         -> `Reading(kind="Scalar")`
  - `waveform`     (DBR_DOUBLE count > 1)      -> `Reading(kind="Array")`
  - `enum_value`   (DBR_ENUM)                  -> `Reading(kind="Categorical")`
  - `bad_quality_value` (DBR_DOUBLE + MAJOR alarm at startup)
                                                -> `Reading(quality="Bad")`
  - `slow_value`   (DBR_DOUBLE + getter sleep) -> exercises read timeout

Future tests for `Image` (2D NDArray) ship with the EpicsPvaControlPort
at Stage-1d; CA does not natively carry NTNDArray.

PV names are pure test-shape (`double_value`, etc.); they do NOT
mirror production EPICS conventions at APS 2-BM (`2bma:m1.RBV` /
`32idcSP:`). This module is the in-process test substrate, not a
production-PV-naming fixture.

## xdist isolation

Each test gets its own ephemeral CA server port via
`socket.bind(("127.0.0.1", 0))`. Env vars lock both server-side
(`EPICS_CA_SERVER_PORT`, `EPICS_CAS_*`) and client-side
(`EPICS_CA_ADDR_LIST`, `EPICS_CA_AUTO_ADDR_LIST=NO`) onto loopback
plus that exact port; no broadcast clash between concurrent xdist
workers. Per [[project_test_parallelization]] the suite runs at
`-n 4`.

Env vars MUST be set BEFORE the client's `Context()` is constructed
(caproto reads them at broadcaster init). The fixture sets them via
`monkeypatch` then yields; the adapter creates its `Context` lazily
on first call, which happens inside the test body after the fixture
setup completes.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportArgumentType=false, reportMissingTypeStubs=false

from __future__ import annotations

import asyncio

from caproto import AlarmSeverity, AlarmStatus, ChannelType
from caproto.server import PVGroup, pvproperty


class CoraTestIOC(PVGroup):
    """Test IOC exposing one PV per `ReadingKind` branch + Quality + timeout arms.

    Instantiated with `prefix=<unique-per-test>` so multiple IOCs can
    coexist in the same xdist worker without PV-name collision (in
    practice each test gets its own port + prefix, so collisions
    cannot happen).
    """

    double_value = pvproperty(value=0.0, dtype=float, doc="DBR_DOUBLE scalar")
    long_value = pvproperty(value=0, dtype=int, doc="DBR_LONG scalar")
    string_value = pvproperty(value="initial", dtype=ChannelType.STRING, doc="DBR_STRING scalar")
    waveform = pvproperty(
        value=[0.0, 0.0, 0.0, 0.0],
        dtype=ChannelType.DOUBLE,
        max_length=128,
        doc="DBR_DOUBLE waveform",
    )
    enum_value = pvproperty(
        enum_strings=("off", "on", "fault"),
        dtype=ChannelType.ENUM,
        doc="DBR_ENUM with closed label set",
    )
    bad_quality_value = pvproperty(
        value=99.9,
        dtype=float,
        alarm_group="isolated_bad_quality",
        doc="DBR_DOUBLE permanently in MAJOR alarm; exercises Quality=Bad ACL. "
        "`alarm_group` isolates this PV's alarm state from the PVGroup default: "
        "without it, the startup hook's MAJOR severity bleeds into every other PV.",
    )
    slow_value = pvproperty(
        value=0.0,
        dtype=float,
        doc="DBR_DOUBLE whose getter sleeps; exercises ControlTimeoutError",
    )

    @bad_quality_value.startup
    async def _bad_quality_startup(self, instance, async_lib) -> None:
        _ = async_lib
        await instance.alarm.write(
            severity=AlarmSeverity.MAJOR_ALARM,
            status=AlarmStatus.READ,
        )

    @slow_value.getter
    async def _slow_value_getter(self, instance):
        _ = instance
        await asyncio.sleep(1.0)
        return 0.0
