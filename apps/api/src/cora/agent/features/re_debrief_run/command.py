"""The `ReDebriefRun` command.

Operator-supplied intent dataclass for on-demand RunDebrief
re-invocation. Carries:

  - `run_id`: which Run to debrief. Existence-checked at
    handler-load time (the same `load_run` the subscriber uses).
  - `parent_decision_id`: optional ref to a prior RunDebrief
    `Decision` (the one being re-evaluated). When supplied, the
    new Decision's `parent_id` is set, forming a PROV-O
    `wasInformedBy` chain. Existence + same-Run-scope checked at
    handler.

The Decision's `decision_id` is server-allocated by the handler
from the IdGenerator port (NOT UUID5-derived; the subscriber's
deterministic-id strategy is specific to terminal-event
at-most-once and doesn't apply here -- on-demand calls use the
Idempotency-Key header for at-most-once).

Discovery of the latest RunDebrief Decision for a Run is OUT OF
SCOPE for v1 (operator passes `parent_decision_id` explicitly via
the request body). The discovery query lands when the UI surfaces
a "re-debrief" button that needs to look it up; pre-trigger the
MCP tool is operator-typed.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ReDebriefRun:
    """Re-invoke RunDebrief on demand for the given Run."""

    run_id: UUID
    parent_decision_id: UUID | None = None
