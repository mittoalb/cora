"""Pure decider for the `ActivateClearanceTemplate` command.

Single-source transition: `Draft -> Active`. Strict-not-idempotent.

## Validation

  - State must not be None -> `ClearanceTemplateNotFoundError`
  - Current status must be `Draft` -> `ClearanceTemplateCannotActivateError`
"""

from datetime import datetime

from cora.safety.aggregates.clearance_template import (
    ClearanceTemplate,
    ClearanceTemplateActivated,
    ClearanceTemplateCannotActivateError,
    ClearanceTemplateNotFoundError,
    ClearanceTemplateStatus,
)
from cora.safety.features.activate_clearance_template.command import (
    ActivateClearanceTemplate,
)
from cora.shared.identity import ActorId

_ACTIVATABLE_STATUSES: tuple[ClearanceTemplateStatus, ...] = (ClearanceTemplateStatus.DRAFT,)


def decide(
    state: ClearanceTemplate | None,
    command: ActivateClearanceTemplate,
    *,
    now: datetime,
    activated_by: ActorId,
) -> list[ClearanceTemplateActivated]:
    """Decide the events produced by activating a Draft clearance template.

    Invariants:
      - State must not be None -> ClearanceTemplateNotFoundError
      - Current status must be Draft
        -> ClearanceTemplateCannotActivateError
    """
    if state is None:
        raise ClearanceTemplateNotFoundError(command.template_id)
    if state.status not in _ACTIVATABLE_STATUSES:
        raise ClearanceTemplateCannotActivateError(state.id, state.status)

    return [
        ClearanceTemplateActivated(
            template_id=state.id,
            occurred_at=now,
            activated_by=activated_by,
        )
    ]
