"""Domain events emitted by the Capability aggregate, plus the discriminated union.

New aggregate (no rename history → no dual-match arms). Events:

  - RecipeCapabilityDefined (genesis)
  - RecipeCapabilityVersioned (declarative replacement at new version)
  - RecipeCapabilityDeprecated (terminal state; carries optional
                          replaced_by pointer per LOINC `MAP_TO`)

Status is NOT carried in event payloads — the event type itself
encodes the state change. Same precedent as `FamilyStatus` in
[[project-family-affordance-design]].

## Replacement semantics

Per [[project-capability-aggregate-design]] and the Pattern P lock
in [[project-family-affordance-design]]: a new version IS a new
declaration. RecipeCapabilityVersioned carries the FULL declarative
contract (required_affordances, parameter_schema, executor_shapes)
— every field REPLACES the prior value wholesale. No diff/merge
semantics. Matches Method/Plan/Practice/Family replace-on-version
precedent.

## Payload field ordering

Affordances and executor_shapes serialize as sorted lists of enum
string values for deterministic payload comparison. `replaced_by_
capability_id` serializes as string-or-None.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.equipment.aggregates.family import Affordance
from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.capability.executor_shape import ExecutorShape


@dataclass(frozen=True)
class RecipeCapabilityDefined:
    """A new universal Capability template was defined.

    Status is implicit (`Defined`) — the evolver sets it. All
    declarative fields are present in the genesis payload.
    """

    capability_id: UUID
    code: str
    name: str
    required_affordances: frozenset[Affordance]
    executor_shapes: frozenset[ExecutorShape]
    occurred_at: datetime
    description: str | None = None
    parameter_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class RecipeCapabilityVersioned:
    """A Capability's declarative contract was revised; a new version label was issued.

    Multi-source transition: `Defined | Versioned -> Versioned`. The
    full declarative contract REPLACES wholesale (a new version IS a
    new declaration per Pattern P).
    """

    capability_id: UUID
    version_tag: str
    required_affordances: frozenset[Affordance]
    executor_shapes: frozenset[ExecutorShape]
    occurred_at: datetime
    description: str | None = None
    parameter_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class RecipeCapabilityDeprecated:
    """A Capability was marked as no longer recommended for new bindings.

    Multi-source transition: `Defined | Versioned -> Deprecated`.
    `replaced_by_capability_id` is an optional pointer to a successor
    Capability (LOINC `MAP_TO` precedent); None means deprecated-
    without-replacement. Existing Methods/Procedures that reference
    this Capability are NOT automatically invalidated (advisory at BC
    layer).
    """

    capability_id: UUID
    occurred_at: datetime
    replaced_by_capability_id: UUID | None = None


RecipeCapabilityEvent = (
    RecipeCapabilityDefined | RecipeCapabilityVersioned | RecipeCapabilityDeprecated
)


def event_type_name(event: RecipeCapabilityEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: RecipeCapabilityEvent) -> dict[str, Any]:
    """Serialize a Capability event to a JSON-friendly dict for jsonb storage.

    UUIDs become strings, datetimes ISO-8601, frozensets sorted lists.
    """
    match event:
        case RecipeCapabilityDefined(
            capability_id=capability_id,
            code=code,
            name=name,
            required_affordances=required_affordances,
            executor_shapes=executor_shapes,
            description=description,
            parameter_schema=parameter_schema,
            occurred_at=occurred_at,
        ):
            return {
                "capability_id": str(capability_id),
                "code": code,
                "name": name,
                "description": description,
                "required_affordances": sorted(a.value for a in required_affordances),
                "executor_shapes": sorted(s.value for s in executor_shapes),
                "parameter_schema": parameter_schema,
                "occurred_at": occurred_at.isoformat(),
            }
        case RecipeCapabilityVersioned(
            capability_id=capability_id,
            version_tag=version_tag,
            required_affordances=required_affordances,
            executor_shapes=executor_shapes,
            description=description,
            parameter_schema=parameter_schema,
            occurred_at=occurred_at,
        ):
            return {
                "capability_id": str(capability_id),
                "version_tag": version_tag,
                "description": description,
                "required_affordances": sorted(a.value for a in required_affordances),
                "executor_shapes": sorted(s.value for s in executor_shapes),
                "parameter_schema": parameter_schema,
                "occurred_at": occurred_at.isoformat(),
            }
        case RecipeCapabilityDeprecated(
            capability_id=capability_id,
            replaced_by_capability_id=replaced_by_capability_id,
            occurred_at=occurred_at,
        ):
            return {
                "capability_id": str(capability_id),
                "replaced_by_capability_id": (
                    str(replaced_by_capability_id)
                    if replaced_by_capability_id is not None
                    else None
                ),
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def _load_affordances(payload: dict[str, Any]) -> frozenset[Affordance]:
    """Load required_affordances from payload's list field.

    Tolerates missing key (additive-state default empty), empty list,
    or list of valid Affordance enum value strings. Unknown values
    raise ValueError via the StrEnum constructor (fail-loud).
    """
    raw = payload.get("required_affordances", [])
    return frozenset(Affordance(v) for v in raw)


def _load_executor_shapes(payload: dict[str, Any]) -> frozenset[ExecutorShape]:
    """Load executor_shapes from payload's list field.

    Same fail-loud stance as `_load_affordances`. Note: the evolver
    can fold an empty set here (additive-state default), but the
    decider rejects empty input at write time per Pattern P.
    """
    raw = payload.get("executor_shapes", [])
    return frozenset(ExecutorShape(v) for v in raw)


def from_stored(stored: StoredEvent) -> RecipeCapabilityEvent:
    """Rebuild a Capability event from a StoredEvent loaded from the event store.

    Single-match arms, no legacy/dual-match (this aggregate is new,
    not a rename of a prior aggregate).
    """
    payload = stored.payload
    match stored.event_type:
        case "RecipeCapabilityDefined":
            try:
                return RecipeCapabilityDefined(
                    capability_id=UUID(payload["capability_id"]),
                    code=payload["code"],
                    name=payload["name"],
                    description=payload.get("description"),
                    required_affordances=_load_affordances(payload),
                    executor_shapes=_load_executor_shapes(payload),
                    parameter_schema=payload.get("parameter_schema"),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed RecipeCapabilityDefined payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "RecipeCapabilityVersioned":
            try:
                return RecipeCapabilityVersioned(
                    capability_id=UUID(payload["capability_id"]),
                    version_tag=payload["version_tag"],
                    description=payload.get("description"),
                    required_affordances=_load_affordances(payload),
                    executor_shapes=_load_executor_shapes(payload),
                    parameter_schema=payload.get("parameter_schema"),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed RecipeCapabilityVersioned payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "RecipeCapabilityDeprecated":
            try:
                replaced_raw = payload.get("replaced_by_capability_id")
                return RecipeCapabilityDeprecated(
                    capability_id=UUID(payload["capability_id"]),
                    replaced_by_capability_id=(
                        UUID(replaced_raw) if replaced_raw is not None else None
                    ),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed RecipeCapabilityDeprecated payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case _:
            msg = f"Unknown RecipeCapabilityEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "RecipeCapabilityDefined",
    "RecipeCapabilityDeprecated",
    "RecipeCapabilityEvent",
    "RecipeCapabilityVersioned",
    "event_type_name",
    "from_stored",
    "to_payload",
]
