"""Zone aggregate state, value objects, and domain errors.

`Zone` is the aggregate root for a Trust zone: a grouping of
controlled assets / actors with a homogeneous security policy. Per
ISA-99 a zone is defined by *trust-requirement homogeneity*, not by
physical location, so a Trust Zone is an orthogonal classification
to the Equipment hierarchy (every Asset has both — see BC-map note).

Phase 3a keeps Zone minimal: `id` + `name`. SL-T (Security Level
Target per Foundational Requirement) and status lifecycle
(`Defined → Active → Modified → Archived`, per BC-map status
vocabulary) land in subsequent sub-phases when commands that
exercise them ship — adding fields to a state record that gets
defaulted in the evolver is the additive-change pattern documented
in CONTRIBUTING.md (state-level fields with defaults are free; only
event-payload-level changes need new event types).
"""

from dataclasses import dataclass
from uuid import UUID

ZONE_NAME_MAX_LENGTH = 200


class InvalidZoneNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Zone name must be 1-{ZONE_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class ZoneAlreadyExistsError(Exception):
    """Attempted to define a zone whose stream already has events."""

    def __init__(self, zone_id: UUID) -> None:
        super().__init__(f"Zone {zone_id} already exists")
        self.zone_id = zone_id


class ZoneNotFoundError(Exception):
    """Attempted an operation on a zone whose stream has no events."""

    def __init__(self, zone_id: UUID) -> None:
        super().__init__(f"Zone {zone_id} not found")
        self.zone_id = zone_id


@dataclass(frozen=True)
class ZoneName:
    """Display name for a zone. Trimmed; 1-200 chars."""

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed or len(trimmed) > ZONE_NAME_MAX_LENGTH:
            raise InvalidZoneNameError(self.value)
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class Zone:
    """Aggregate root: a Trust zone definition."""

    id: UUID
    name: ZoneName
