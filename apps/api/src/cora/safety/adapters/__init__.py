"""Adapters Safety BC ships for cross-BC ports.

Today: `PostgresClearanceLookup` implementing
`cora.infrastructure.ports.ClearanceLookup` (consumed by Run BC's
`start_run` handler).
"""

from cora.safety.adapters.postgres_clearance_lookup import PostgresClearanceLookup

__all__ = ["PostgresClearanceLookup"]
