"""Federation BC subscriber registration for the projection worker.

Reserved for federation-specific subscribers (for example, a
grant-counter on `PermitDefined` for ABI-tier-floor audit, or a
publish-pull pump on `SealPointerSigned`). Empty in Stage 2a; the
first subscriber lands when its driving slice ships in Stage 2b/2c.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.projection.registry import ProjectionRegistry


def register_federation_subscribers(
    registry: ProjectionRegistry,
    deps: Kernel,
) -> None:
    """Register every Federation-owned subscriber on the worker registry."""
    _ = registry
    _ = deps


__all__ = ["register_federation_subscribers"]
