"""Adapters Safety BC ships for cross-aggregate / cross-BC ports.

- `PostgresClearanceLookup` implementing `ClearanceLookup` (consumed
  by Run BC's `start_run` handler).
- `PostgresClearanceTemplateLookup` implementing `ClearanceTemplateLookup`
  (consumed by Safety BC's own `version_clearance_template` handler
  for parent-chain validation; 9E extends consumers to
  `register_clearance` / `amend_clearance`).
"""

from cora.safety.adapters.postgres_clearance_lookup import PostgresClearanceLookup
from cora.safety.adapters.postgres_clearance_template_lookup import (
    PostgresClearanceTemplateLookup,
)

__all__ = ["PostgresClearanceLookup", "PostgresClearanceTemplateLookup"]
