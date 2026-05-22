"""The `VersionCapability` command — intent dataclass for this slice.

Multi-source transition: Defined | Versioned -> Versioned. Operators
issue a new version_tag (free text like "v2", "2026-Q3") to mark a
revision of the declarative contract.

The supplied required_affordances, executor_shapes, description, and
parameter_schema REPLACE the prior wholesale (a new version IS a new
declaration Pattern P; matches Method/Plan/Practice/Family
replace-on-version precedent). All declarative fields are REQUIRED on
version_capability (executor_shapes must be non-empty; the others can
be empty/None).
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from cora.equipment.aggregates.family import Affordance
from cora.recipe.aggregates.capability import ExecutorShape


@dataclass(frozen=True)
class VersionCapability:
    """Issue a new version label + replacement declarative contract for an existing Capability."""

    capability_id: UUID
    version_tag: str
    required_affordances: frozenset[Affordance]
    executor_shapes: frozenset[ExecutorShape]
    description: str | None = None
    parameter_schema: dict[str, Any] | None = None
