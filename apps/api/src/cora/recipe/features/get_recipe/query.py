"""The `GetRecipe` query, intent dataclass for this read slice.

Mirrors `GetCapability` / `GetMethod` / `GetPlan`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetRecipe:
    """Read the current state of an existing Recipe by id."""

    recipe_id: UUID
