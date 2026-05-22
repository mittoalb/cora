"""The `AdjustRun` command — intent dataclass for this slice.

Carries the caller-controlled inputs for mid-flight parameter steering:
  - `run_id` — the target Run (existence verified at handler-load time).
  - `parameter_patch` — RFC 7396 JSON Merge Patch on top of the Run's
    current `effective_parameters`. Non-empty required (empty patches
    silently no-op and mislead the audit; rejected at the decider with
    `InvalidRunAdjustPatchError`).
  - `reason` — operator-supplied free-text justification (1-500 chars
    after trim; mirrors RunAbortReason / RunStopReason / RunTruncateReason
    + ClearanceRejectReason precedent). Required: steering without
    recorded intent is the abort+restart anti-pattern relocated.
  - `decided_by_decision_id` — OPTIONAL link to the Decision BC record
    that justified this adjustment. Domain-meaningful Decision-causation
    on the event payload, distinct from the technical envelope
    `causation_id` (previous-message chain). Maps to
    `prov:wasInformedBy` at the future PROV-O export adapter (same
    export contract used by `Decision.parent_id`). Operators can
    record ad-hoc adjustments without a Decision; not every steering
    action needs formal justification at MVP. NO existence check at
    decider per the cross-BC eventual-consistency stance.

Strict scope (per design memo lock): `adjust_run` is parameter
mutation only. Subject / Plan / Method / Asset binding / `triggered_by`
/ `raid` / `campaign_id` / `external_refs` are NOT touched — those
are identity / scientific-intent changes that force abort + restart
by design. The line keeps "what experiment ran" coherent across the
audit.

Server-side concerns (wall-clock timestamp, correlation id, per-event
ids) are injected by the handler from infrastructure ports.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class AdjustRun:
    """Adjust a Run's effective parameters mid-flight."""

    run_id: UUID
    parameter_patch: dict[str, Any]
    reason: str
    decided_by_decision_id: UUID | None = None
