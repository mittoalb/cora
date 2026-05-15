"""The `StartProcedure` command -- intent dataclass for this slice.

Single-source genesis transition: `Defined -> Running`. Carries only
the target Procedure id; everything else (name, kind, target Asset
refs, parent_run_id) was set at register_procedure time. The handler
pre-loads each target Asset via `load_asset` to build a
`ProcedureStartContext` for the decider's Decommissioned-state guard
(mirror of RunStartContext from 6f-1).

Server-side concerns (wall-clock timestamp, correlation id, per-event
ids) are injected by the handler from infrastructure ports.

Status is implicit at start (`Running`) and not part of the command --
see Procedure aggregate's `state.py` docstring for the enum-in-state,
derived-from-event-type-in-evolver convention.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class StartProcedure:
    """Transition an existing Procedure from Defined to Running."""

    procedure_id: UUID
