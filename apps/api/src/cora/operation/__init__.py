"""Operation bounded context.

Owns episodic operational work in CORA (ISA-106 lens):

  - `Procedure` aggregate (10c-a): one execution of an episodic
    operational task — bakeout, calibration sweep, optical alignment,
    beam-mode change, recovery procedure, ID maintenance, KB
    switching. Each Procedure has sequenced steps; each step has a
    Setpoint / Action / Check triplet (CORA's rename of ISA-106's
    canonical Command/Perform/Verify to avoid catastrophic CQRS
    collision).

Track B BC (ISA-106 lens). Independent of Track A (Recipe / Subject
/ Data). Distinct from ISA-88 batch operations which the Run BC
follows; the BC is named `Operation` (publicly committed in BC map +
phase plan) despite the ISA-88 naming overlap (ISA-88 has Operation
as mid-tier in P -> UP -> Op -> Phase). The collision is
documented + manageable; renaming the publicly-committed BC name was
rejected as too high churn for marginal value. See
[[project_operation_design]] §Locks for the rename-rejection
rationale.

Phase 10c-a ships the BC scaffold + 2 slices:
  - register_procedure (genesis -> Defined)
  - get_procedure (read; fold-on-read)

Phase 10c-b adds start_procedure / complete_procedure / abort_procedure
plus the per-step substream (Setpoint/Action/Check rows on
entries_operation_procedure_steps, mirroring 6f-5b RunReading).
Phase 10c-c adds projection + list_procedures + truncate_procedure
(and Held/Resumed only if pilot needs surface).
"""

from cora.operation.errors import UnauthorizedError
from cora.operation.routes import register_operation_routes
from cora.operation.tools import register_operation_tools
from cora.operation.wire import OperationHandlers, wire_operation

__all__ = [
    "OperationHandlers",
    "UnauthorizedError",
    "register_operation_routes",
    "register_operation_tools",
    "wire_operation",
]
