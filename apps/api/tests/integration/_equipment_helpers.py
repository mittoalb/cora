"""Shared helpers for Equipment BC PG integration tests.

The Mount/Frame PG integration test files share an identical
`placement(parent_frame_id)` constructor and projection-drain wrapper;
hoisted here so per-file boilerplate stays short.

Per-file helpers that vary (the `_seed_*` family, scenario-specific
fixtures) stay local to each test file. Only the genuinely-identical
shared pieces live here.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates._placement import (
    Placement,
    ReferenceSurface,
    UnitSystem,
)
from cora.infrastructure.projection import ProjectionRegistry, drain_projections

if TYPE_CHECKING:
    from uuid import UUID

    import asyncpg


def placement(parent_frame_id: UUID) -> Placement:
    """A minimal Placement adequate for any slot in PG integration tests.

    Pins the parent_frame_id; everything else is canonical zero / SI_MM_RAD
    so test-side construction stays terse. Tests that need a specific
    pose construct Placement directly rather than calling this helper.
    """
    return Placement(
        x=0.0,
        y=0.0,
        z=0.0,
        rx=0.0,
        ry=0.0,
        rz=0.0,
        parent_frame_id=parent_frame_id,
        reference_surface=ReferenceSurface.SHIELDING_FACE,
        tol_x=0.1,
        tol_y=0.1,
        tol_z=0.1,
        tol_rx=0.0,
        tol_ry=0.0,
        tol_rz=0.0,
        units=UnitSystem.SI_MM_RAD,
    )


async def drain_equipment_projections(
    pool: asyncpg.Pool,
    *,
    deadline_seconds: float = 2.0,
) -> None:
    """Construct a fresh ProjectionRegistry, register Equipment's projections,
    and drain pending events to the projection workers' bookmarks.
    """
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(pool, registry, deadline_seconds=deadline_seconds)


__all__ = ["drain_equipment_projections", "placement"]
