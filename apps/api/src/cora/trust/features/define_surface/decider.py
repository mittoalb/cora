"""Pure decider for the `DefineSurface` command."""

from datetime import datetime
from uuid import UUID

from cora.trust.aggregates.surface import (
    Surface,
    SurfaceAlreadyExistsError,
    SurfaceDefined,
    SurfaceName,
)
from cora.trust.features.define_surface.command import DefineSurface


def decide(
    state: Surface | None,
    command: DefineSurface,
    *,
    now: datetime,
    new_id: UUID,
) -> list[SurfaceDefined]:
    """Decide the events produced by defining a new surface.

    Invariants:
      - State must be None (defensive AlreadyExists guard against
        UUID collision) -> SurfaceAlreadyExistsError
      - Name must be valid -> InvalidSurfaceNameError
        (via SurfaceName VO)
    """
    if state is not None:
        raise SurfaceAlreadyExistsError(state.id)
    name = SurfaceName(command.name)  # validates + trims
    return [
        SurfaceDefined(
            surface_id=new_id,
            name=name.value,
            kind=command.kind,
            occurred_at=now,
        ),
    ]
