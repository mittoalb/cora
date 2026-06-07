"""The `AppendCalibrationRevision` command — intent dataclass for this slice.

Carries caller-controlled inputs for appending a new revision to an
existing Calibration:

  - `calibration_id` — target Calibration aggregate. Existence
    verified at handler-load time; misses raise
    `CalibrationNotFoundError` at the decider.
  - `value` — JSON-shaped dict with the revision's measured/computed/
    asserted value. Validated STRICT against the calibration's
    quantity-specific `VALUE_SCHEMA`.
  - `status` — `Provisional` or `Verified`. A 2-tier ladder; a
    3-tier `Refined` is a future option, not currently supported.
  - `source` — typed `CalibrationSource` discriminated union
    (`MeasuredSource(procedure_id)` | `ComputedSource(dataset_id)` |
    `AssertedSource(asserted_by)`). The runtime type IS the discriminator;
    no redundant `source_kind` field. Source FK targets are NOT
    cross-BC validated at the decider (eventual-consistency stance).
  - `decided_by_decision_id` — OPTIONAL link to the Decision BC record
    that justified this revision (cross-Plan pivot, agent advisory).
    Mirrors AdjustRun / StartRun / AbortRun pattern.
  - `supersedes_revision_id` — OPTIONAL direct derivation edge to a
    prior revision on the SAME aggregate that this revision supersedes.
    Cross-aggregate supersession is forbidden; the supersedes target
    must exist in `aggregate.revisions` at append time.

Server-side concerns (revision_id, wall-clock timestamp, correlation
id, per-event ids, established_by) are injected by the handler from
infrastructure ports / the request envelope.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from cora.calibration.aggregates.calibration import (
    CalibrationSource,
    CalibrationStatus,
)


@dataclass(frozen=True)
class AppendCalibrationRevision:
    """Append a new revision to an existing Calibration."""

    calibration_id: UUID
    value: dict[str, Any]
    status: CalibrationStatus
    source: CalibrationSource
    decided_by_decision_id: UUID | None = None
    supersedes_revision_id: UUID | None = None
