"""Domain events emitted by the ClearanceTemplate aggregate.

Event type: `ClearanceTemplateDefined` (genesis; status=Draft implicit).
Future events (9B+9C): `ClearanceTemplateActivated`, `ClearanceTemplateVersioned`,
`ClearanceTemplateDeprecated`, `ClearanceTemplateWithdrawn`.

Status is NOT carried in event payloads -- the event type itself encodes the
state change. The evolver hardcodes the mapping per match arm.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class ClearanceTemplateDefined:
    """A new clearance template was defined.

    Status is implicit (`Draft`) -- the evolver sets it.
    `version` defaults to 1 (day-one field for schema stability).
    `supersedes_template_id` defaults to None (set by version events in 9B).
    """

    template_id: UUID
    facility_code: str
    code: str
    title: str
    occurred_at: datetime
    defined_by: UUID
    version: int = 1
    supersedes_template_id: UUID | None = None
    external_ref: str | None = None


# Type alias for future extensibility (9B+9C events will be added here)
ClearanceTemplateEvent = ClearanceTemplateDefined


def event_type_name(event: ClearanceTemplateEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: ClearanceTemplateEvent) -> dict[str, Any]:
    """Serialize a ClearanceTemplate event to a JSON-friendly dict for jsonb storage."""
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
            return {
                "template_id": str(template_id),
                "facility_code": facility_code,
                "code": code,
                "title": title,
                "occurred_at": occurred_at.isoformat(),
                "defined_by": str(defined_by),
                "version": version,
                "supersedes_template_id": str(supersedes_template_id)
                if supersedes_template_id is not None
                else None,
                "external_ref": external_ref,
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> ClearanceTemplateEvent:
    """Rebuild a ClearanceTemplate event from a StoredEvent loaded from the event store."""
    payload = stored.payload
    match stored.event_type:
        case "ClearanceTemplateDefined":
            return deserialize_or_raise(
                "ClearanceTemplateDefined",
                lambda: ClearanceTemplateDefined(
                    template_id=UUID(payload["template_id"]),
                    facility_code=payload["facility_code"],
                    code=payload["code"],
                    title=payload["title"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                    defined_by=UUID(payload["defined_by"]),
                    version=payload.get("version", 1),
                    supersedes_template_id=UUID(payload["supersedes_template_id"])
                    if payload.get("supersedes_template_id") is not None
                    else None,
                    external_ref=payload.get("external_ref"),
                ),
            )
        case _:
            msg = f"Unknown ClearanceTemplateEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "ClearanceTemplateDefined",
    "ClearanceTemplateEvent",
    "event_type_name",
    "from_stored",
    "to_payload",
]
