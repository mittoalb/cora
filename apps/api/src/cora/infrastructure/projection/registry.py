"""Registry of registered Projections (and future Subscriber kinds).

The composition root populates this during lifespan setup by calling
each BC's `register_<bc>_projections(registry, deps)` function. The
worker iterates the registry; the test suite uses it to drive the
`drain_projections` helper and the arch-fitness `every-registration-
has-a-table` check.
"""

from collections.abc import Iterator

from cora.infrastructure.projection.handler import Projection


class DuplicateProjectionError(Exception):
    """Raised when two projections register with the same name. Names
    must be unique because they key the bookmark row + the proj_* table
    + the arch-fitness checks."""

    def __init__(self, name: str) -> None:
        super().__init__(
            f"Projection with name {name!r} is already registered. "
            "Names must be unique across the whole process; they key "
            "the bookmark row and the proj_* table."
        )
        self.name = name


class ProjectionRegistry:
    """Holds the set of registered projections; iterable by the worker."""

    def __init__(self) -> None:
        self._by_name: dict[str, Projection] = {}

    def register(self, projection: Projection) -> None:
        if projection.name in self._by_name:
            raise DuplicateProjectionError(projection.name)
        self._by_name[projection.name] = projection

    def get(self, name: str) -> Projection | None:
        return self._by_name.get(name)

    def names(self) -> frozenset[str]:
        return frozenset(self._by_name)

    def is_empty(self) -> bool:
        return not self._by_name

    def __iter__(self) -> Iterator[Projection]:
        return iter(self._by_name.values())

    def __len__(self) -> int:
        return len(self._by_name)


__all__ = ["DuplicateProjectionError", "ProjectionRegistry"]
