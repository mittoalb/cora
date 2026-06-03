"""The `ConductProcedure` command -- operator-facing entry for `Conductor.conduct()`.

Unlike most slice commands, `ConductProcedure` does not directly write
to an aggregate's event stream. It hands control to the
`cora.operation.conductor.Conductor` runtime, which orchestrates
the full Procedure lifecycle: `start_procedure` ->
walk-supplied-steps -> `complete_procedure` (on success) or
`abort_procedure` (on step failure). The handler returns a
`ConductProcedureResult` summarising the run; failures are encoded in
that result, not raised as exceptions, so a single HTTP / MCP
response shape covers every outcome the operator needs to triage.

`steps` is the caller-supplied sequence the Conductor walks.
Substrate-agnostic: setpoint addresses parse inside the routed
`ControlPort` adapter, action names look up in the `ActionRegistry`,
check criteria evaluate against the read `Reading.value`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from cora.operation.conductor import ConductorFailure, Step


@dataclass(frozen=True)
class ConductProcedure:
    """Invoke the Conductor against an existing Procedure + step list."""

    procedure_id: UUID
    steps: Sequence[Step]


@dataclass(frozen=True)
class ConductProcedureResult:
    """Summary of a `ConductProcedure` invocation.

    Mirrors `ConductorResult` shape verbatim (procedure_id +
    completed_count + optional failure) so the wire response stays
    decoupled from the in-process Conductor type and the
    application-layer slice owns its return-type contract.
    """

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    failure: ConductorFailure | None = None
