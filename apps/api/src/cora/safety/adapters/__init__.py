"""Adapters Safety BC ships for cross-BC ports.

Today: `PostgresClearanceLookup` implementing
`cora.infrastructure.ports.ClearanceLookup` (consumed by Run BC's
`start_run` handler from Phase 11a-c-3).
"""

from cora.safety.adapters.clearance_lookup_pg import PostgresClearanceLookup

__all__ = ["PostgresClearanceLookup"]
