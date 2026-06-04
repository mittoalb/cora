"""Adapters Recipe BC ships for cross-BC ports.

Today: `PostgresCapabilityLookup` implementing
`cora.infrastructure.ports.CapabilityLookup` (consumed by Equipment
BC's `get_asset_integration_view` handler for the applicable-
Capabilities slice of the read-time integration bundle).
"""

from cora.recipe.adapters.postgres_capability_lookup import PostgresCapabilityLookup

__all__ = ["PostgresCapabilityLookup"]
