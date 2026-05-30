"""Domain events emitted by the Frame aggregate, plus the discriminated union.

Mirrors the locked event-module shape (see
`apps/api/src/cora/equipment/aggregates/asset/events.py`): event
classes as frozen dataclasses, discriminated union,
`event_type_name`, `to_payload`, `from_stored` with per-arm
KeyError / TypeError / AttributeError wrapping into tagged
ValueError per `project_from_stored_wrap_convention`.

Event catalog:
  - `FrameRegistered` (genesis)
  - `FrameUpdated` (placement mutation; no-op on equal at the
    decider via `make_asset_update_handler`)
  - `FrameDecommissioned` (terminal lifecycle)

## Payload conventions for Frame

`status` is NOT carried in the payload: the event TYPE encodes the
state change (`FrameRegistered -> Active`,
`FrameDecommissioned -> Decommissioned`). Same precedent as Asset
and Subject.

`parent_frame_id` IS carried in the `FrameRegistered` payload as
`UUID | None`. Root frames serialize None; child frames serialize a
string.

`placement_relative_to_parent` IS carried in both `FrameRegistered`
(initial value) and `FrameUpdated` (new value) payloads. Serialized
as the Placement VO's full 15-field shape (or `None` for root frames
in `FrameRegistered`).

`reason` on `FrameDecommissioned` is operator-supplied free text;
validated 1-500 chars at the API boundary, the decider trusts the
input. Mirrors `AssetDegraded.reason` precedent.

`survey` on `FrameUpdated` is an optional structured payload
(instrument + technician + residual) when the update is a re-survey
rather than a nominal-from-drawing initial set. The VO shape is
intentionally left open until the first survey adapter lands; the
field is `dict[str, Any] | None` for now. Watch item in the design
memo.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.equipment.aggregates._placement import Placement, ReferenceSurface, UnitSystem
from cora.infrastructure.ports.event_store import StoredEvent


def _placement_to_payload(placement: Placement) -> dict[str, Any]:
    """Serialize a Placement VO to a JSON-friendly dict."""
    return {
        "x": placement.x,
        "y": placement.y,
        "z": placement.z,
        "rx": placement.rx,
        "ry": placement.ry,
        "rz": placement.rz,
        "parent_frame": str(placement.parent_frame),
        "reference_surface": placement.reference_surface.value,
        "tol_x": placement.tol_x,
        "tol_y": placement.tol_y,
        "tol_z": placement.tol_z,
        "tol_rx": placement.tol_rx,
        "tol_ry": placement.tol_ry,
        "tol_rz": placement.tol_rz,
        "units": placement.units.value,
    }


def _placement_from_payload(payload: dict[str, Any]) -> Placement:
    """Reconstruct a Placement VO from its JSON payload.

    Raises KeyError / TypeError / AttributeError on malformed input;
    callers wrap these into tagged ValueError per the from_stored
    convention.
    """
    return Placement(
        x=payload["x"],
        y=payload["y"],
        z=payload["z"],
        rx=payload["rx"],
        ry=payload["ry"],
        rz=payload["rz"],
        parent_frame=UUID(payload["parent_frame"]),
        reference_surface=ReferenceSurface(payload["reference_surface"]),
        tol_x=payload["tol_x"],
        tol_y=payload["tol_y"],
        tol_z=payload["tol_z"],
        tol_rx=payload["tol_rx"],
        tol_ry=payload["tol_ry"],
        tol_rz=payload["tol_rz"],
        units=UnitSystem(payload["units"]),
    )


@dataclass(frozen=True)
class FrameRegistered:
    """A new frame was registered.

    Status is implicit (`Active`); the evolver sets it.
    `parent_frame_id` and `placement_relative_to_parent` go together:
    both None for root frames, both non-None for child frames. The
    decider's `InvalidFrameRootError` guard enforces the invariant.
    """

    frame_id: UUID
    name: str
    parent_frame_id: UUID | None
    placement_relative_to_parent: Placement | None
    occurred_at: datetime


@dataclass(frozen=True)
class FrameUpdated:
    """A frame's `placement_relative_to_parent` was updated.

    Used both for nominal-from-drawing initial corrections and for
    re-survey updates. When `survey` is present, the payload carries
    survey provenance (instrument identifier, technician identifier,
    measured residual); when absent, the update is operator-asserted
    without measurement provenance.

    No-op at the decider when the new placement equals the current
    one (idempotent contract via `make_asset_update_handler`); an
    event in the stream means the placement actually changed.

    Root frames cannot be updated via this event (their
    `placement_relative_to_parent` is None by invariant; updating
    would violate the root-vs-child invariant). The decider rejects
    `FrameUpdated` on root frames.
    """

    frame_id: UUID
    new_placement: Placement
    survey: dict[str, Any] | None
    occurred_at: datetime


@dataclass(frozen=True)
class FrameDecommissioned:
    """A frame was retired from the coordinate hierarchy.

    Terminal lifecycle transition: `Active -> Decommissioned`.
    Strict semantics: re-decommissioning raises
    `FrameCannotDecommissionError` at the decider rather than no-op'ing.
    The handler's projection precondition (`frame_consumers`) is what
    guards against orphaning consumers; this event being in the
    stream means no active consumer referenced the frame at write
    time.

    `reason` is operator-supplied free text.
    """

    frame_id: UUID
    reason: str
    occurred_at: datetime


FrameEvent = FrameRegistered | FrameUpdated | FrameDecommissioned


def event_type_name(event: FrameEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: FrameEvent) -> dict[str, Any]:
    """Serialize a Frame event to a JSON-friendly dict for jsonb storage."""
    match event:
        case FrameRegistered(
            frame_id=frame_id,
            name=name,
            parent_frame_id=parent_frame_id,
            placement_relative_to_parent=placement,
            occurred_at=occurred_at,
        ):
            return {
                "frame_id": str(frame_id),
                "name": name,
                "parent_frame_id": (str(parent_frame_id) if parent_frame_id is not None else None),
                "placement_relative_to_parent": (
                    _placement_to_payload(placement) if placement is not None else None
                ),
                "occurred_at": occurred_at.isoformat(),
            }
        case FrameUpdated(
            frame_id=frame_id,
            new_placement=new_placement,
            survey=survey,
            occurred_at=occurred_at,
        ):
            return {
                "frame_id": str(frame_id),
                "new_placement": _placement_to_payload(new_placement),
                "survey": survey,
                "occurred_at": occurred_at.isoformat(),
            }
        case FrameDecommissioned(
            frame_id=frame_id,
            reason=reason,
            occurred_at=occurred_at,
        ):
            return {
                "frame_id": str(frame_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> FrameEvent:
    """Rebuild a Frame event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.
    Per-arm `(KeyError, TypeError, AttributeError)` wrap into tagged
    ValueError per `project_from_stored_wrap_convention`.
    """
    payload = stored.payload
    match stored.event_type:
        case "FrameRegistered":
            try:
                raw_parent = payload["parent_frame_id"]
                raw_placement = payload["placement_relative_to_parent"]
                return FrameRegistered(
                    frame_id=UUID(payload["frame_id"]),
                    name=payload["name"],
                    parent_frame_id=UUID(raw_parent) if raw_parent is not None else None,
                    placement_relative_to_parent=(
                        _placement_from_payload(raw_placement)
                        if raw_placement is not None
                        else None
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed FrameRegistered payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "FrameUpdated":
            try:
                return FrameUpdated(
                    frame_id=UUID(payload["frame_id"]),
                    new_placement=_placement_from_payload(payload["new_placement"]),
                    survey=payload.get("survey"),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed FrameUpdated payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "FrameDecommissioned":
            try:
                return FrameDecommissioned(
                    frame_id=UUID(payload["frame_id"]),
                    reason=payload["reason"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed FrameDecommissioned payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case _:
            msg = f"Unknown FrameEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "FrameDecommissioned",
    "FrameEvent",
    "FrameRegistered",
    "FrameUpdated",
    "event_type_name",
    "from_stored",
    "to_payload",
]
