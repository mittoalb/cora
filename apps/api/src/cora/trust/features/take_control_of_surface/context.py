"""Cross-aggregate context the `take_control_of_surface` decider validates against.

Built by the handler from one preload: the
`proj_trust_surface_active_visit` row for the target Surface
(`active_holder`) -- "who drives this Surface right now?" -- read via
`load_surface_active_visit(deps.pool, surface_id)`.
"""

from dataclasses import dataclass

from cora.trust.projections.surface_active_visit import SurfaceActiveVisit


@dataclass(frozen=True)
class TakeControlOfSurfaceContext:
    """Snapshot of the Surface's current controller at command time."""

    active_holder: SurfaceActiveVisit | None
