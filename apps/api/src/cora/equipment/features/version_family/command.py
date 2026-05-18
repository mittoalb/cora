"""The `VersionFamily` command — intent dataclass for this slice.

Multi-source transition: Defined | Versioned -> Versioned. Operators
issue a new version_tag (free text like "v2", "2026-Q3") to mark a
revision of the device-class definition.

`affordances` is REQUIRED at version time per DLM-A: a new version
IS a new declaration. The supplied set REPLACES the prior affordance
set wholesale (no diff/merge semantics). Empty `frozenset()` is a
valid argument when the operator intends to clear all affordances at
the new version; the explicit empty supply is the discipline.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates.family import Affordance


@dataclass(frozen=True)
class VersionFamily:
    """Issue a new version label + replacement affordance set for an existing Family."""

    family_id: UUID
    version_tag: str
    affordances: frozenset[Affordance]
