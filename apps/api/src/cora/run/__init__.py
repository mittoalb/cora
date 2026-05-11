"""Run bounded context.

Owns the actual-execution layer of CORA. Per the BC map's recipe
ladder, Run is the keystone — Method (≈ ISA-88 General Recipe) →
Practice (≈ Site Recipe) → Plan (≈ Master/Control Recipe) → **Run**
(actual batch execution; immutable, has FSM, audit trail, references
to Subject(s)).

A Run binds a `Plan` (which itself binds a Practice + Asset set)
and an optional `Subject` (sample being measured; null for dark-
field / flat-field calibration runs per beamline-domain convention,
where calibration data is consumed alongside sample data within the
same analysis pipeline).

Track A BC. Depends on:
  - `Recipe.Plan` (referenced by `Run.plan_id`; loaded at Run-start
    for re-validation of capability superset against current Asset
    state)
  - `Equipment.Asset` (transitive via Plan; loaded at Run-start to
    re-check that no bound Asset has been Decommissioned)
  - `Subject.Subject` (referenced by `Run.subject_id` if non-null;
    must be in Mounted or Measured state)

## Phase 6f-1 scope

Minimal Run:
  - `id` + `name` (RunName: 11th bounded-name VO)
  - `plan_id: UUID` — eventual-consistency ref; existence verified
    at handler-load time
  - `subject_id: UUID | None` — null for calibration / dark-field
    runs; if non-null, Subject must be in Mounted | Measured
  - `status: RunStatus` (`Started` only at 6f-1)

Cross-aggregate validation at Run-start (gate-review Q2 / Q5
locked answers): handler pre-loads Plan + Subject (if subject_id)
+ each bound Asset (from `plan.asset_ids`); decider receives
`RunStartContext` and validates as opaque domain inputs (same
canonical pattern as Plan's PlanBindingContext from 6e-1). Per
gate-review Q5: Run-start re-validates capability superset
against CURRENT Asset state (Plan-bind validated against then-
current; drift is real, Run is the last gate).

Phase history (✅ all shipped except 6f-2+ and Supply/Decision
integration):
  - 6f-1: Run + start_run + get_run (the keystone slice)
  - 6f-2 (deferred): Active-phase transitions (Completed, Aborted)
  - 6f-3 (deferred): Hold/Resume/Stop transitions
  - 6f-4 (deferred): Truncated terminal + truncation-reason design
  - 6f-5 (deferred): First substream infrastructure + per-frame
    trigger substream (high-cardinality telemetry)

Known gaps (pre-6f-1 sequencing decisions, gate-review Q3 locked):
  - **Supply availability check** (Track B Supply BC not shipped):
    Run-start does NOT verify beam / power / gas availability today.
    Operator-trusted; documented as gap. Lands when Supply BC ships.
  - **Decision approval check** (Decision BC not shipped):
    Run-start does NOT require an Approved Decision referencing
    the Plan today. Operator-trusted; documented as gap. Lands
    when Decision BC ships.

Layout (mirrors Recipe / Equipment / Trust / Subject):
    aggregates/run/           -- aggregate state, events union, evolver, read
    features/<verb>_<noun>/   -- vertical slice: command/query + decider? + handler + route + tool
    wire.py                   -- RunHandlers bundle + wire_run(deps)
    routes.py                 -- register_run_routes(app)
    tools.py                  -- register_run_tools(mcp, *, get_handlers)
"""

from cora.run.errors import UnauthorizedError
from cora.run.routes import register_run_routes
from cora.run.tools import register_run_tools
from cora.run.wire import RunHandlers, wire_run

__all__ = [
    "RunHandlers",
    "UnauthorizedError",
    "register_run_routes",
    "register_run_tools",
    "wire_run",
]
