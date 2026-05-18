"""ExecutorShape closed v1 StrEnum: which executor kinds may implement a Capability.

Phase 6m (folded into 6k per DLM-B). Per
[[project-capability-aggregate-design]] and Round 3 of
[[project-capability-research]]:

- A `Capability` is the universal declarative template; concrete
  implementations come in heterogeneous executor shapes.
- Closed v1: exactly two shapes: `Method` (Recipe BC, heavyweight
  science chain — Method→Plan→Run) and `Procedure` (Operation BC,
  lightweight ceremony chain per 10c, ISA-106 Setpoint/Action/Check
  atoms).
- New shapes only via explicit rule-of-three trigger (three concrete
  candidates of a new shape attested in production); never ad-hoc
  per [[project-capability-research]] anti-hook 17.

## Why closed v1

AAS Capability Submodel's open enumeration (program/task/operation
mode/service/procedure/...) was a documented governance failure
that contributed to the submodel's withdrawal. CORA's closed two-
shape policy is the safe slice of a known-good pattern. New shapes
add real complexity (each carries its own FSM, validation, ports);
gating them behind rule-of-three keeps the catalog disciplined.

## Module location

Lives in Recipe BC alongside Capability (`cora.recipe.aggregates
.capability.executor_shape`). Operation BC's Procedure imports
this cross-BC at 10d's Procedure.start guard. The dependency
direction is Recipe → Operation (Operation depends on Recipe's
enum), NOT the reverse. Tach enforces.
"""

from enum import StrEnum


class ExecutorShape(StrEnum):
    """Closed v1 enum of executor kinds that may implement a Capability."""

    METHOD = "Method"
    """Heavyweight science executor: Method (Recipe BC) → Plan → Run.

    Used for Capabilities that produce datasets (continuous-rotation
    sweep, mosaic acquisition, dark/flat baseline, energy change,
    first-light, etc.). The Method-chain shape carries asset binding
    (Plan.wiring), parameter validation (Method.parameters_schema as
    binding under Capability.parameter_schema), and lifecycle FSM
    (Run states).
    """

    PROCEDURE = "Procedure"
    """Lightweight ceremony executor: Procedure (Operation BC) per 10c.

    Used for Capabilities that orchestrate operational ceremony
    without producing datasets (motor homing, hexapod reboot,
    sample mount/dismount, alignment cycles, dewar lifecycle). The
    Procedure shape carries ISA-106 Setpoint/Action/Check atoms and
    its own FSM (Defined → Running → Completed | Aborted | Truncated).
    """


__all__ = ["ExecutorShape"]
