"""Pure decider for the `RegisterClearance` command.

Pure function: given the current Clearance state (None for a fresh
stream) and a `RegisterClearance` command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from the
Clock and IdGenerator ports (the non-determinism principle: capture,
don't recompute).

## Validation

  - State must be None (genesis-only) -> `ClearanceAlreadyExistsError`
  - `title` validated 1-200 chars via `ClearanceTitle` VO ->
    `InvalidClearanceTitleError`
  - `bindings` must be non-empty (a Clearance with zero bindings can
    never gate anything) -> `InvalidClearanceBindingsError`
  - `external_id`, when provided, validated 1-100 chars after trim ->
    `InvalidClearanceExternalIdError`
  - `valid_from >= valid_until` (when both provided) ->
    `InvalidClearanceValidityWindowError`. Equality is rejected because
    a zero-duration window can never be "active" (any sensible Run.start
    gate checks `valid_from <= now < valid_until`).
  - Each `declarations[i].target` MUST be a member of `bindings` ->
    `InvalidClearanceDeclarationTargetError`. The Clearance gates against
    its bindings; declarations claim hazards against specific binding
    targets within that set. A target outside the binding set is
    incoherent.
  - `bindings` and `declarations` VO-internal validation already runs
    at construction (Identifier fields inside ExternalRefBinding,
    HazardDeclaration mitigations, notes); re-validation here would be
    redundant.

Initial status is implicit `Defined` (event type IS the state-change
indicator; the genesis evolver hardcodes the mapping). Per the
cross-aggregate genesis convention.

`parent_id` is always None for `register_clearance` (the amendment
slice sets it; this slice is genesis-only).
"""

from datetime import datetime
from uuid import UUID

from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceAlreadyExistsError,
    ClearanceRegistered,
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
from cora.safety.features.register_clearance.command import RegisterClearance


def decide(
    state: Clearance | None,
    command: RegisterClearance,
    *,
    now: datetime,
    new_id: UUID,
) -> list[ClearanceRegistered]:
    """Decide the events produced by registering a new clearance.

    Invariants:
      - State must be None (genesis-only)
        -> ClearanceAlreadyExistsError
      - Title must be valid -> InvalidClearanceTitleError
        (via ClearanceTitle VO)
      - bindings must be non-empty -> InvalidClearanceBindingsError
      - external_id (when set) must be valid
        -> InvalidClearanceExternalIdError
      - valid_from must be strictly less than valid_until (when both
        provided) -> InvalidClearanceValidityWindowError
      - Each declaration.target must be in bindings
        -> InvalidClearanceDeclarationTargetError
    """
    if state is not None:
        raise ClearanceAlreadyExistsError(state.id)

    # Validate + trim title via VO (raises InvalidClearanceTitleError on bad input)
    title = ClearanceTitle(command.title)

    # Bindings must be non-empty
    if not command.bindings:
        raise InvalidClearanceBindingsError("at least one binding required")

    # Validate external_id when provided
    external_id: str | None
    if command.external_id is None:
        external_id = None
    else:
        trimmed = command.external_id.strip()
        if not trimmed or len(trimmed) > CLEARANCE_EXTERNAL_ID_MAX_LENGTH:
            raise InvalidClearanceExternalIdError(command.external_id)
        external_id = trimmed

    # Validity window must be strictly increasing when both provided.
    # Equality (zero-duration window) is rejected: any sensible Run.start
    # gate checks `valid_from <= now < valid_until`, so an equal-bounds
    # window can never be active. Reject early so degenerate Clearances
    # don't sit in the projection.
    if (
        command.valid_from is not None
        and command.valid_until is not None
        and command.valid_from >= command.valid_until
    ):
        raise InvalidClearanceValidityWindowError(command.valid_from, command.valid_until)

    # Each declaration's target binding must be a member of the Clearance's
    # bindings set. Subset semantic per the design memo's HazardDeclaration
    # documentation; declarations referencing out-of-scope targets are
    # incoherent and would silently corrupt the gating story.
    for declaration in command.declarations:
        if declaration.target not in command.bindings:
            raise InvalidClearanceDeclarationTargetError(declaration.target)

    # Pre-serialize bindings + declarations for the event payload tuple
    bindings_payload = tuple(serialize_binding(b) for b in command.bindings)
    declarations_payload = tuple(serialize_declaration(d) for d in command.declarations)

    return [
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
            parent_id=None,
            occurred_at=now,
        )
    ]
