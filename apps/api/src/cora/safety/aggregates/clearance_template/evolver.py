"""Evolver: replay events to reconstruct ClearanceTemplate state.

Status mapping per event type:
  - `ClearanceTemplateDefined`    -> DRAFT      (genesis; version=1)
  - `ClearanceTemplateActivated`  -> ACTIVE     (transition; version unchanged)
  - `ClearanceTemplateVersioned`  -> status unchanged (additive within Active;
                                     bumps version + sets supersedes_template_id)
  - `ClearanceTemplateDeprecated` -> DEPRECATED (transition; version unchanged)
  - `ClearanceTemplateWithdrawn`  -> WITHDRAWN  (terminal transition)

The event type IS the state-change indicator (no status field in event payloads).

Transition events applied to empty state raise ValueError.
"""

from collections.abc import Sequence
from dataclasses import replace
from typing import assert_never

from cora.safety.aggregates.clearance_template.events import (
    ClearanceTemplateActivated,
    ClearanceTemplateDefined,
    ClearanceTemplateDeprecated,
    ClearanceTemplateEvent,
    ClearanceTemplateVersioned,
    ClearanceTemplateWithdrawn,
)
from cora.safety.aggregates.clearance_template.state import (
    ClearanceTemplate,
    ClearanceTemplateCode,
    ClearanceTemplateStatus,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId


def evolve(state: ClearanceTemplate | None, event: ClearanceTemplateEvent) -> ClearanceTemplate:
    """Apply one event to the current state."""
    match event:
        case ClearanceTemplateDefined(
            template_id=template_id,
            facility_code=facility_code,
            code=code,
            title=title,
            occurred_at=occurred_at,
            defined_by=defined_by,
            version=version,
            supersedes_template_id=supersedes_template_id,
            external_ref=external_ref,
        ):
            _ = state  # ClearanceTemplateDefined is the genesis event; prior state ignored
            return ClearanceTemplate(
                id=template_id,
                facility_code=FacilityCode(facility_code),
                code=ClearanceTemplateCode(code),
                title=ClearanceTemplateTitle(title),
                defined_at=occurred_at,
                defined_by=ActorId(defined_by),
                status=ClearanceTemplateStatus.DRAFT,
                version=ClearanceTemplateVersion(version),
                supersedes_template_id=supersedes_template_id,
                external_ref=external_ref,
            )
        case ClearanceTemplateActivated():
            if state is None:
                msg = "ClearanceTemplateActivated requires prior ClearanceTemplateDefined"
                raise ValueError(msg)
            return replace(state, status=ClearanceTemplateStatus.ACTIVE)
        case ClearanceTemplateVersioned(
            new_version=new_version,
            supersedes_template_id=supersedes_template_id,
        ):
            if state is None:
                msg = "ClearanceTemplateVersioned requires prior ClearanceTemplateDefined"
                raise ValueError(msg)
            return replace(
                state,
                version=ClearanceTemplateVersion(new_version),
                supersedes_template_id=supersedes_template_id,
            )
        case ClearanceTemplateDeprecated():
            if state is None:
                msg = "ClearanceTemplateDeprecated requires prior ClearanceTemplateDefined"
                raise ValueError(msg)
            return replace(state, status=ClearanceTemplateStatus.DEPRECATED)
        case ClearanceTemplateWithdrawn():
            if state is None:
                msg = "ClearanceTemplateWithdrawn requires prior ClearanceTemplateDefined"
                raise ValueError(msg)
            return replace(state, status=ClearanceTemplateStatus.WITHDRAWN)
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[ClearanceTemplateEvent]) -> ClearanceTemplate | None:
    """Replay a stream of events from the empty initial state."""
    state: ClearanceTemplate | None = None
    for event in events:
        state = evolve(state, event)
    return state


__all__ = ["evolve", "fold"]
