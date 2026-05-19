"""The `DefineSurface` command — intent dataclass for this slice."""

from dataclasses import dataclass

from cora.trust.aggregates.surface import SurfaceKind


@dataclass(frozen=True)
class DefineSurface:
    """Define a new arrival Surface."""

    name: str
    kind: SurfaceKind
