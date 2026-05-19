"""Surface aggregate state, value objects, and domain errors.

A `Surface` is a process-level arrival point — the protocol-bound
socket through which a request entered CORA's process. v1 values:
HTTP, MCP stdio, MCP streamable-http. Distinct from `Conduit` (which
is an ISA-99/IEC-62443 inter-zone topology primitive); v2 memo
locked the decomposition after the Stage 1 v1 conflation was caught
by R2C — see memory/project_conduit_injection_design.md AH13.

Status FSM (`Defined → Versioned → Deprecated`) matches the
Capability / Family / Practice / Method / Plan / Agent post-Phase-3
convention. Lifecycle transitions are future-loadable; v1 ships
genesis only (per AH8).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.infrastructure.bounded_text import validate_bounded_text
from cora.trust.aggregates.surface.surface_kind import SurfaceKind

SURFACE_NAME_MAX_LENGTH = 200


class InvalidSurfaceNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Surface name must be 1-{SURFACE_NAME_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class SurfaceAlreadyExistsError(Exception):
    """Attempted to define a surface whose stream already has events."""

    def __init__(self, surface_id: UUID) -> None:
        super().__init__(f"Surface {surface_id} already exists")
        self.surface_id = surface_id


@dataclass(frozen=True)
class SurfaceName:
    """Display name for a surface. Trimmed; 1-200 chars."""

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=SURFACE_NAME_MAX_LENGTH,
            error_class=InvalidSurfaceNameError,
        )
        object.__setattr__(self, "value", trimmed)


class SurfaceStatus(StrEnum):
    """Lifecycle states. v1 only emits DEFINED; the other values are
    pre-shipped so versioning / deprecation slices can land additively
    later without breaking the state shape."""

    DEFINED = "defined"
    VERSIONED = "versioned"
    DEPRECATED = "deprecated"


@dataclass(frozen=True)
class Surface:
    """Aggregate root: a process-level arrival surface."""

    id: UUID
    name: SurfaceName
    kind: SurfaceKind
    status: SurfaceStatus
    defined_at: datetime
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None
