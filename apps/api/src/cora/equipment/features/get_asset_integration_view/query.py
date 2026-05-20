"""The `GetAssetIntegrationView` query — intent dataclass for this read slice.

Queries are dataclasses just like commands. Mirrors `GetAsset` /
`GetFamily` / `GetSubject` / `GetActor`. The query carries only the
input the caller controls; the application handler adds context
(correlation_id, principal_id) at call time.

Phase 1B v1 of the MTP-style read-model bundle. See
[[project-asset-integration-view-design]] for the locked shape.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetAssetIntegrationView:
    """Read the integration-view bundle for an existing asset by id."""

    asset_id: UUID
