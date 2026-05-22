"""Adapters Caution BC ships for cross-BC ports.

Today: `PostgresCautionLookup` implementing
`cora.infrastructure.ports.CautionLookup` (consumed by Run BC's
`start_run` handler for the non-blocking acknowledged-cautions
snapshot on `RunStarted`).
"""

from cora.caution.adapters.caution_lookup_pg import PostgresCautionLookup

__all__ = ["PostgresCautionLookup"]
