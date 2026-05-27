"""PvDriver port: substrate-agnostic wire access for the Operation BC executor.

`PvDriver` is the async Protocol that Operation BC slice handlers
(and the future Procedure executor) use to read, write, and
subscribe to EPICS-family Process Variables. Substrate details
(libca via aioca, pvxs via p4p, sans-I/O via caproto) live behind
concrete adapters; the executor never touches `aioca` /
`p4p.client.thread` / `caproto` symbols directly.

Per [[project_control_port_design]], BC-tier port (lives here, not at
`cora.infrastructure.ports`) until a second consumer BC needs it. The
rule-of-three promotion criteria is documented in
[[project_adapter_naming_design]].

Substrate scope: pragmatically EPICS-shaped at v1. `PvValue.kind` and
`alarm_severity` mirror EPICS V4 Normative Types + the CA 4-value
alarm enum. Future `TangoPvDriver` / `OpcUaPvDriver` may extend the
kind enum additively. RPC / method abstraction is intentionally out of
scope; when Tango Commands or OPC UA Methods are needed, add a
separate port per the design lock's anti-hook.

Per [[project_normative_types_research]], NT vocabulary stays inside
`EpicsPvaPvDriver` only. `PvValue` is the CORA-neutral boundary that
the executor sees.

## Adapters

`InMemoryPvDriver` (this Stage-1a, unit-tier per
[[project_test_infra]]'s 5-tier pyramid) ships alongside this port.
Production-substrate adapters (`CaprotoPvDriver`, `EpicsCaPvDriver`,
`EpicsPvaPvDriver`) land in Stage-1b through Stage-1d. Per-PV adapter
dispatch through `PvDriverRegistry` lands in Stage-1e.

## Exceptions

Six exception classes mirror CORA's standard exception families.
PvDriver is not REST-accessible, so these don't map to HTTP statuses;
the executor's decider captures them as event-payload metadata per
[[project_non_determinism_principle]].

## Subscribe shape

`subscribe` returns an `AsyncIterator[PvValue]` after async setup
(connect-and-register-as-subscriber). Caller iterates with
`async for v in await driver.subscribe(pv):`. Adapter may coalesce
intermediate values on subscriber lag (p4p Qt keep-last convention);
EpicsPvaPvDriver documents its policy in implementation notes.
Mid-stream disconnect raises `PvNotConnectedError` through the
iterator so silent stream pause is impossible.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

PvKind = Literal["scalar", "array", "enum", "table"]
"""Tagged-union discriminator for `PvValue`.

v1 set covers EPICS V4 NTScalar / NTScalarArray / NTEnum / NTTable.
Extensible by tag addition when a future substrate lands: Tango
DevState likely fits `enum`; OPC UA `LocalizedText` may justify a
new `localized_text` tag. Adding a tag is additive; consumers that
already pattern-match keep working until they want the new shape.
"""


PvAlarmSeverity = Literal["NONE", "MINOR", "MAJOR", "INVALID"]
"""EPICS CA 4-value alarm enum lifted verbatim.

Honest framing per design lock: `PvValue` is CORA-internal but
currently EPICS-flavored. A future `TangoPvDriver` may need to add
variants or surface alarms through a different shape; today's lock
keeps the value set tight and EPICS-aligned.
"""


@dataclass(frozen=True)
class PvValue:
    """CORA-neutral typed wrapper for a PV's current value plus metadata.

    Adapter-side NT unpacking (`EpicsPvaPvDriver`) or CA primitive
    coercion (`EpicsCaPvDriver`) flattens substrate-specific types
    into this tagged union. `value` is `Any` because the runtime
    shape varies with `kind`: scalar is `int | float | bool | str`,
    array is a tuple, enum is a string label, table is a dict of
    column names to tuples. Callers narrow per kind at the use site.

    NT optional structures (valueAlarm / displayLimit / controlLimit)
    are intentionally NOT surfaced here. They are presentation hints,
    not control-plane data; adapters drop them at unpacking time.

    `sampled_at` is `phenomenonTime` (when the IOC observed the
    value). `alarm_status` is adapter-specific and opaque at the
    port layer; treat it as a forensic breadcrumb, not a value to
    branch on.
    """

    kind: PvKind
    value: Any
    sampled_at: datetime
    alarm_severity: PvAlarmSeverity = "NONE"
    alarm_status: str = ""


class PvNotConnectedError(Exception):
    """No active CA/PVA channel for this PV.

    Triggered on pre-connect call OR mid-call / mid-stream
    disconnect. `subscribe` iterators raise this through the
    iterator (not via silent pause) so the caller decides to retry
    (re-call `subscribe`) or close.
    """

    def __init__(self, pv: str) -> None:
        super().__init__(f"PV {pv!r} not connected")
        self.pv = pv


class PvTimeoutError(Exception):
    """Adapter timeout elapsed before the operation completed.

    Triggered when put-callback did not fire under `wait=True`, a
    get exceeded its timeout, or initial connect timed out. Carries
    the timeout that was breached so logs distinguish "we waited X
    seconds and gave up" from generic latency complaints.
    """

    def __init__(self, pv: str, timeout_s: float) -> None:
        super().__init__(f"PV {pv!r} operation exceeded {timeout_s}s")
        self.pv = pv
        self.timeout_s = timeout_s


class PvPutFailedError(Exception):
    """IOC rejected the write.

    Triggered on a read-only PV, invalid value type for the PV's
    Normative Type, or IOC-level access-security denial expressed
    as a put-callback failure. Distinct from `PvAccessDeniedError`
    so adapters can preserve the IOC's failure-mode distinction.
    """

    def __init__(self, pv: str, reason: str) -> None:
        super().__init__(f"PV {pv!r} put rejected: {reason}")
        self.pv = pv
        self.reason = reason


class PvTypeCoercionError(Exception):
    """Adapter cannot unpack the substrate value into a `PvValue` tag.

    Triggered when `EpicsPvaPvDriver` sees a novel NT structure or
    `EpicsCaPvDriver` sees a CA primitive that does not fit the
    closed `PvKind` set. Carries the substrate's raw type label so
    operators can extend the tag set in a follow-up rather than
    silently dropping data.
    """

    def __init__(self, pv: str, raw_type: str, target_kind: str) -> None:
        super().__init__(
            f"PV {pv!r} value of type {raw_type!r} cannot coerce to kind {target_kind!r}"
        )
        self.pv = pv
        self.raw_type = raw_type
        self.target_kind = target_kind


class PvAccessDeniedError(Exception):
    """IOC denied access via CA security policy or PVA auth.

    Distinct from `PvPutFailedError` so operators distinguish "wrong
    value, IOC said no" from "you may not touch this PV at all." Per
    [[project_control_port_design]] watch item 9, IOC-level ACLs are
    defense-in-depth; CORA's authz primary lives at the executor /
    Conduit layer.
    """

    def __init__(self, pv: str) -> None:
        super().__init__(f"PV {pv!r} access denied")
        self.pv = pv


class NoAdapterForPvError(Exception):
    """`PvDriverRegistry` has no route matching this PV name.

    Triggered when the executor asks the registry for a route and no
    configured prefix matches. Almost always a configuration gap (a
    new IOC was added without extending `pv_bindings` on the relevant
    Assets, or the registry routes were not updated for a new
    substrate). Lives here, alongside the port, so adapters that
    construct registries can raise it; the registry class itself
    ships in Stage-1e.
    """

    def __init__(self, pv: str) -> None:
        super().__init__(f"PV {pv!r} has no matching adapter in PvDriverRegistry")
        self.pv = pv


@runtime_checkable
class PvDriver(Protocol):
    """Wire-protocol port for EPICS-family control systems.

    Substrate-agnostic. Concrete adapters (`InMemoryPvDriver`,
    `CaprotoPvDriver`, `EpicsCaPvDriver`, `EpicsPvaPvDriver`)
    implement the wire details. Per
    [[project_non_determinism_principle]], port-injected effects are
    captured in the executor's event payloads at decider time.

    Port shape follows the ros2_control "keep port dumb, executor
    pluggable" lesson from [[project_control_port_research]] R2.
    Adapter internals may use asyncio (aioca, p4p asyncio client) or
    threading (p4p thread client, caproto sync backend); the surface
    callers see is `async def get` / `async def put` /
    `async def subscribe`.

    The executor that consumes this Protocol stays open at v1: PvDriver
    composes with fixed-rate-tick (BT-style), async event-driven, and
    plain-async executor architectures. Stage-2 picks an initial
    executor shape; PvDriver is not coupled to that pick.
    """

    async def get(self, pv: str) -> PvValue:
        """Read the current value of `pv`.

        Raises `PvNotConnectedError` if there is no active channel or
        `PvTimeoutError` if the read exceeds the adapter timeout.
        """
        ...

    async def put(
        self,
        pv: str,
        value: int | float | bool | str | tuple[Any, ...],
        *,
        wait: bool = True,
        timeout_s: float = 30.0,
    ) -> None:
        """Write `value` to `pv`.

        `wait=True` (the default) blocks until the IOC's put-callback
        fires, i.e. caput-callback semantics. `wait=False` returns as
        soon as the write is enqueued.

        Raises `PvNotConnectedError`, `PvTimeoutError` (when
        `wait=True` and the callback does not fire in time),
        `PvPutFailedError` (IOC rejected the write), or
        `PvAccessDeniedError` (IOC denied access).
        """
        ...

    async def subscribe(self, pv: str) -> AsyncIterator[PvValue]:
        """Subscribe to value changes on `pv`. Caller iterates the result.

        Returned `AsyncIterator` yields one `PvValue` per update.
        Caller pattern is `async for v in await driver.subscribe(pv):`
        (the outer `await` runs the connect-and-register-as-subscriber
        setup, then the `async for` drains updates).

        On mid-stream disconnect the iterator raises
        `PvNotConnectedError` so silent stream pause is impossible.
        The caller decides whether to re-subscribe or close.

        Subscriber-responsible back-pressure. Adapters MAY coalesce
        intermediate values on lag (p4p Qt keep-last convention);
        `EpicsPvaPvDriver` documents its policy in implementation
        notes. Cancellation is via the iterator's `aclose()`.
        """
        ...


__all__ = [
    "NoAdapterForPvError",
    "PvAccessDeniedError",
    "PvAlarmSeverity",
    "PvDriver",
    "PvKind",
    "PvNotConnectedError",
    "PvPutFailedError",
    "PvTimeoutError",
    "PvTypeCoercionError",
    "PvValue",
]
