"""Pure decider for the `AppendRevision` command (Phase 12a-2).

Append-only growth: takes the loaded Calibration state (loaded by the
handler) and produces a single `CalibrationRevisionAppended` event.
No FSM transition; status lives per-revision per the design memo.

## Validation order

  1. State must not be None → `CalibrationNotFoundError`.
  2. `value` validated STRICT against the calibration's quantity-
     specific `VALUE_SCHEMA` via the shared
     `validate_values_against_schema(no_schema_message=...)` helper;
     misses surface as `InvalidCalibrationValueError`.
  3. If `supersedes_revision_id` is provided: must reference a revision
     already present in `state.revisions`. Cross-aggregate supersession
     forbidden; misses surface as `SupersedesRevisionNotFoundError`.
  4. Source FK targets (procedure_id / dataset_id / actor_id depending
     on the union arm) are NOT cross-BC validated here per the
     eventual-consistency stance (matches adjust_run + Trust.Conduit +
     Asset parent + Procedure target + Campaign lead_actor + Run.subject
     precedent).

`established_by_actor_id` is handler-injected from the request
envelope's `principal_id`. The source's typed inner UUID may or may
not match the envelope's principal (an operator can assert a value
on behalf of another operator; a subscriber can append a computed
revision while the envelope's principal is the system identity).

`revision_id` is handler-injected from the IdGenerator port (separate
from the event_id which envelope-wraps the persisted event).

Quantity-string is read off the loaded aggregate; the caller cannot
override (revisions inherit the calibration's quantity by definition).
"""

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from cora.calibration.aggregates.calibration import (
    Calibration,
    CalibrationNotFoundError,
    CalibrationRevisionAppended,
    InvalidCalibrationValueError,
    SupersedesRevisionNotFoundError,
    serialize_source,
)
from cora.calibration.features.append_revision.command import AppendRevision
from cora.calibration.quantities import CalibrationQuantity, get_value_schema
from cora.infrastructure.json_schema_validation import validate_values_against_schema


def decide(
    state: Calibration | None,
    command: AppendRevision,
    *,
    now: datetime,
    new_revision_id: UUID,
    established_by_actor_id: UUID,
) -> list[CalibrationRevisionAppended]:
    """Decide the events produced by appending a new revision."""
    if state is None:
        raise CalibrationNotFoundError(command.calibration_id)

    # Resolve the quantity enum from the aggregate's value-string.
    # Closed-catalog invariant: the string MUST round-trip through the
    # StrEnum; a fold-time mismatch would have failed earlier.
    quantity = CalibrationQuantity(state.quantity)
    value_schema = get_value_schema(quantity)
    _validate_value(command.value, value_schema)

    if command.supersedes_revision_id is not None and not any(
        r.revision_id == command.supersedes_revision_id for r in state.revisions
    ):
        raise SupersedesRevisionNotFoundError(state.id, command.supersedes_revision_id)

    # Encode the polymorphic source into the exclusive-arc payload
    # fields via the public cross-slice helper (Q5 lock).
    arc = serialize_source(command.source)

    return [
        CalibrationRevisionAppended(
            revision_id=new_revision_id,
            calibration_id=state.id,
            value=command.value,
            status=command.status,
            source_procedure_id=_uuid_or_none(arc["source_procedure_id"]),
            source_dataset_id=_uuid_or_none(arc["source_dataset_id"]),
            source_actor_id=_uuid_or_none(arc["source_actor_id"]),
            established_at=now,
            established_by_actor_id=established_by_actor_id,
            decided_by_decision_id=command.decided_by_decision_id,
            supersedes_revision_id=command.supersedes_revision_id,
            occurred_at=now,
        )
    ]


def _validate_value(value: dict[str, Any], schema: dict[str, Any]) -> None:
    """STRICT value validation against the quantity's schema."""
    validate_values_against_schema(
        value,
        schema,
        error_class=InvalidCalibrationValueError,
        no_schema_message=(
            "value cannot be validated without a registered schema "
            "(quantity registry invariant violated: keys={keys})"
        ),
    )
    _reject_empty_against_required(value, schema, InvalidCalibrationValueError)


def _reject_empty_against_required(
    values: dict[str, Any],
    schema: dict[str, Any],
    error_class: type[ValueError],
) -> None:
    """Raise when `values` is empty AND `schema` declares any required keys.

    The shared `validate_values_against_schema` helper accepts empty +
    non-None schema by design (required-field enforcement is delegated
    to the per-aggregate consumer); for Calibration's operating_point
    and value dicts we want empty rejected because empty would either
    collide with another calibration on the UNIQUE constraint or
    produce a value-less revision.
    """
    if values:
        return
    raw_required = schema.get("required")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if not isinstance(raw_required, list) or not raw_required:  # pyright: ignore[reportUnknownArgumentType]
        return
    required = cast("list[str]", raw_required)  # pyright: ignore[reportUnknownArgumentType]
    msg = f"cannot be empty; the schema requires keys: {sorted(required)!r}"
    raise error_class(msg)


def _uuid_or_none(raw: str | None) -> UUID | None:
    """Coerce the exclusive-arc string-id back to UUID for the event class."""
    return UUID(raw) if raw is not None else None


__all__ = ["decide"]
