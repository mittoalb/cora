"""Domain events for the Fixture aggregate.

Single-event aggregate per the Visit-instance pattern in the design
memo: one stream per fixture_id, exactly one `FixtureRegistered`
event per stream. No further mutating slices in v1.

## Payload conventions

`slot_asset_bindings` serializes as a sorted list of 2-tuple dicts
(`{slot_name, asset_id}`) for canonical-byte-equality across runs;
`from_stored` rebuilds the frozenset via the SlotAssetBinding VO
constructor.

`assembly_content_hash` is a snapshot captured by the decider, NOT
a runtime back-reference. The Fixture stays interpretable when the
underlying Assembly is versioned or deprecated.

`parameter_overrides` is operator-supplied dict already validated
against the Assembly's `parameter_overrides_schema` at decide-time;
on disk it is opaque JSON.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.equipment.aggregates.fixture.state import SlotAssetBinding
from cora.infrastructure.event_payload import deserialize_or_raise
from cora.infrastructure.ports.event_store import StoredEvent


def _binding_to_payload(binding: SlotAssetBinding) -> dict[str, Any]:
    return {
        "slot_name": binding.slot_name,
        "asset_id": str(binding.asset_id),
    }


def _binding_from_payload(payload: dict[str, Any]) -> SlotAssetBinding:
    return SlotAssetBinding(
        slot_name=payload["slot_name"],
        asset_id=UUID(payload["asset_id"]),
    )


@dataclass(frozen=True)
class FixtureRegistered:
    """A Fixture was registered against an Assembly blueprint.

    Genesis event for the Fixture stream. Carries the full slot
    binding set and the parameter_overrides captured at registration.
    The referenced Assets are NOT mutated; they pre-exist and the
    event simply records the mapping.
    """

    fixture_id: UUID
    assembly_id: UUID
    assembly_content_hash: str
    surface_id: UUID
    slot_asset_bindings: frozenset[SlotAssetBinding]
    parameter_overrides: dict[str, Any]
    occurred_at: datetime


FixtureEvent = FixtureRegistered


def event_type_name(event: FixtureEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: FixtureEvent) -> dict[str, Any]:
    """Serialize a Fixture event to a JSON-friendly dict."""
    match event:
        case FixtureRegistered(
            fixture_id=fixture_id,
            assembly_id=assembly_id,
            assembly_content_hash=assembly_content_hash,
            surface_id=surface_id,
            slot_asset_bindings=slot_asset_bindings,
            parameter_overrides=parameter_overrides,
            occurred_at=occurred_at,
        ):
            return {
                "fixture_id": str(fixture_id),
                "assembly_id": str(assembly_id),
                "assembly_content_hash": assembly_content_hash,
                "surface_id": str(surface_id),
                "slot_asset_bindings": sorted(
                    (_binding_to_payload(b) for b in slot_asset_bindings),
                    key=lambda d: (d["slot_name"], d["asset_id"]),
                ),
                "parameter_overrides": parameter_overrides,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> FixtureEvent:
    """Rebuild a Fixture event from a StoredEvent."""
    payload = stored.payload
    match stored.event_type:
        case "FixtureRegistered":

            def _build() -> FixtureRegistered:
                return FixtureRegistered(
                    fixture_id=UUID(payload["fixture_id"]),
                    assembly_id=UUID(payload["assembly_id"]),
                    assembly_content_hash=payload["assembly_content_hash"],
                    surface_id=UUID(payload["surface_id"]),
                    slot_asset_bindings=frozenset(
                        _binding_from_payload(b) for b in payload["slot_asset_bindings"]
                    ),
                    parameter_overrides=payload["parameter_overrides"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )

            return deserialize_or_raise("FixtureRegistered", _build)
        case _:
            msg = f"Unknown FixtureEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "FixtureEvent",
    "FixtureRegistered",
    "event_type_name",
    "from_stored",
    "to_payload",
]
