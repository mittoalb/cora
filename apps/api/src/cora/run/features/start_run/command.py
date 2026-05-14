"""The `StartRun` command — intent dataclass for this slice.

Carries the caller-controlled inputs:
  - `name` — display name for the new Run (for example "32-ID
    FlyScan morning session" or "Dark field calibration 2026-05-11")
  - `plan_id` — the Plan being executed (eventual-consistency ref;
    existence verified at handler-load time)
  - `subject_id` — the Subject being measured, or None for
    calibration / dark-field runs
  - `raid` — Research Activity Identifier (ISO 23527) for the
    project this Run belongs to. Optional; opaque string carried
    verbatim. Added in 7d to support cross-facility provenance
    export (DataCite / RAiD ecosystem); pre-7d Runs have raid=None
    and stay valid via the forward-compatible payload load.
  - `parameter_overrides` (post-6g-c) — operator-supplied overrides
    on top of `Plan.parameter_defaults`. Applied via RFC 7396 merge
    by the handler before the decider validates against the owning
    Method's `parameters_schema`. Default `{}`.
  - `triggered_by` (post-6g-c) — operator-supplied free text
    capturing what initiated this Run (operator-manual, scheduler,
    prior-run, automation). Optional. Future Decision-BC integration
    may populate this.

Server-side concerns (new aggregate id, wall-clock timestamp,
correlation id, per-event ids) are injected by the handler from
infrastructure ports.

Status is implicit at start (`Running`) and not part of the
command — see Run aggregate's `state.py` docstring for the
enum-in-state, derived-from-event-type-in-evolver convention.

The handler additionally pre-loads Plan + Subject (if given) +
each bound Asset (from `plan.asset_ids`) to build a
`RunStartContext` for the decider (gate-review Q2 / Q5 pattern),
AND resolves the Method's parameters_schema for 6g-c validation.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class StartRun:
    """Start a new Run: bind a Plan + (optional) Subject."""

    name: str
    plan_id: UUID
    subject_id: UUID | None
    raid: str | None = None
    parameter_overrides: dict[str, Any] = field(default_factory=dict[str, Any])
    triggered_by: str | None = None
