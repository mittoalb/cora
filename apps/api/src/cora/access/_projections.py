"""Access BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_access_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry with every Access BC
projection. New projections are added here as a one-line
`registry.register(...)` call.

Lives outside `wire.py` to keep handler-wiring and projection-wiring
separated (handlers go on app.state.access; projections go on the
worker's registry).
"""

from cora.access.projections import ActorSummaryProjection
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry


def register_access_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Access-owned projection on the worker registry.

    `deps` is accepted (and currently unused) so projections that need
    Kernel-supplied collaborators can take them at construction time.
    Today's `ActorSummaryProjection` is stateless beyond its name +
    subscribed_event_types so `deps` stays unused.
    """
    _ = deps  # reserved for future projections needing Kernel collaborators
    registry.register(ActorSummaryProjection())


__all__ = ["register_access_projections"]
