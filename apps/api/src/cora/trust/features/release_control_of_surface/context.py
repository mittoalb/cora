"""Cross-aggregate context the `release_control_of_surface` decider validates against.

Built by the handler from one preload: the
`proj_trust_surface_active_visit` row for the target Surface.
"""

from dataclasses import dataclass

from cora.trust.projections.surface_active_visit import SurfaceActiveVisit


@dataclass(frozen=True)
class ReleaseControlOfSurfaceContext:
    """Snapshot of the Surface's current controller at command time."""

    active_holder: SurfaceActiveVisit | None
