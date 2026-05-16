"""Pure decider for the `AmendClearance` command.

Cross-aggregate transition: parent goes `Active -> Superseded` while a
new child clearance is registered with `parent_clearance_id=<parent>`.
Both event streams are written atomically by the handler via
`EventStore.append_streams`; the decider returns BOTH event lists
typed as `AmendmentEvents` so the handler doesn't need to guess which
stream gets which event.

## Validation

  - Parent state must be Active -> `ClearanceCannotAmendError`
  - Child fields validated identically to `register_clearance` decider
    (title 1-200, bindings non-empty, external_id 1-100 if provided,
    validity-window strict-increasing if both provided, each
    declaration target in child bindings).

The amending actor's id lives on the envelope; the decider neither
reads nor writes it.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceCannotAmendError,
    ClearanceRegistered,
    ClearanceStatus,
    ClearanceSuperseded,
    ClearanceTitle,
    InvalidClearanceBindingsError,
    InvalidClearanceDeclarationTargetError,
    InvalidClearanceExternalIdError,
    InvalidClearanceValidityWindowError,
)
from cora.safety.aggregates.clearance.events import (
    serialize_binding,
    serialize_declaration,
)
from cora.safety.aggregates.clearance.state import (
    CLEARANCE_EXTERNAL_ID_MAX_LENGTH,
)
from cora.safety.features.amend_clearance.command import AmendClearance
from cora.safety.features.amend_clearance.context import ClearanceAmendmentContext

_AMENDABLE_STATUSES: tuple[ClearanceStatus, ...] = (ClearanceStatus.ACTIVE,)


@dataclass(frozen=True)
class AmendmentEvents:
    """The two event lists produced by an amendment, one per stream.

    `parent_events`: appended to the parent clearance's stream.
    `child_events`: appended to the (new) child clearance's stream.

    Both lists are non-empty under normal operation; the handler hands
    them to `EventStore.append_streams` as a single atomic batch.
    """

    parent_events: list[ClearanceSuperseded]
    child_events: list[ClearanceRegistered]


def decide(
    state: Clearance | None,
    command: AmendClearance,
    *,
    context: ClearanceAmendmentContext,
    now: datetime,
    new_id: UUID,
) -> AmendmentEvents:
    """Decide the parent+child events produced by amending an Active clearance.

    `state` is conceptually the child's prior state (always None
    because the child is being created here). The parent's state lives
    in `context.parent`.
    """
    _ = state  # The child is genesis; this slice never sees a prior child state.

    parent = context.parent
    if parent.status not in _AMENDABLE_STATUSES:
        raise ClearanceCannotAmendError(parent.id, parent.status)

    # ---- Validate the child's fields (mirrors register_clearance decider) ----

    title = ClearanceTitle(command.title)

    if not command.bindings:
        raise InvalidClearanceBindingsError("at least one binding required")

    external_id: str | None
    if command.external_id is None:
        external_id = None
    else:
        trimmed = command.external_id.strip()
        if not trimmed or len(trimmed) > CLEARANCE_EXTERNAL_ID_MAX_LENGTH:
            raise InvalidClearanceExternalIdError(command.external_id)
        external_id = trimmed

    if (
        command.valid_from is not None
        and command.valid_until is not None
        and command.valid_from >= command.valid_until
    ):
        raise InvalidClearanceValidityWindowError(command.valid_from, command.valid_until)

    for declaration in command.declarations:
        if declaration.target not in command.bindings:
            raise InvalidClearanceDeclarationTargetError(declaration.target)

    bindings_payload = tuple(serialize_binding(b) for b in command.bindings)
    declarations_payload = tuple(serialize_declaration(d) for d in command.declarations)

    parent_events = [
        ClearanceSuperseded(
            clearance_id=parent.id,
            by_clearance_id=new_id,
            occurred_at=now,
        )
    ]
    child_events = [
        ClearanceRegistered(
            clearance_id=new_id,
            kind=command.kind.value,
            facility_asset_id=command.facility_asset_id,
            title=title.value,
            bindings=bindings_payload,
            declarations=declarations_payload,
            risk_band=command.risk_band.value if command.risk_band is not None else None,
            external_id=external_id,
            valid_from=command.valid_from,
            valid_until=command.valid_until,
            parent_clearance_id=parent.id,
            occurred_at=now,
        )
    ]
    return AmendmentEvents(parent_events=parent_events, child_events=child_events)
