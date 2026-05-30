"""Federation BC's projection-registration entry point.

The composition root (`cora.api.main`) calls
`register_federation_projections(registry, deps)` during the FastAPI
lifespan to populate the worker's registry. Federation owns three
read models, one per aggregate:

  - `PermitSummaryProjection`     -> `proj_federation_permit_summary`
    (PermitDefined / PermitActivated / PermitSuspended / PermitResumed /
    PermitRevoked)
  - `CredentialSummaryProjection` -> `proj_federation_credential_summary`
    (CredentialRegistered / CredentialRotationStarted /
    CredentialRotationCompleted / CredentialRotationAborted /
    CredentialRevoked)
  - `SealProjection`              -> `proj_federation_seal`
    (SealInitialized / SealPointerSigned / SealOnlineKeyRotated /
    SealRepublishingStarted / SealRepublishingCompleted)
"""

from cora.federation.projections import (
    CredentialSummaryProjection,
    PermitSummaryProjection,
    SealProjection,
)
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry


def register_federation_projections(
    registry: ProjectionRegistry,
    deps: Kernel | None = None,
) -> None:
    """Register every Federation-owned projection on the worker registry."""
    _ = deps
    registry.register(PermitSummaryProjection())
    registry.register(CredentialSummaryProjection())
    registry.register(SealProjection())


__all__ = ["register_federation_projections"]
