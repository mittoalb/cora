"""Vertical slices for the Supply BC.

Slices:
  - `register_supply`        (genesis -> Unknown; create-style)
  - `mark_supply_available`  (Unknown -> Available; operator first observation)
  - `get_supply`             (read side)
  - `list_supplies`          (read side)

Degradation/recovery cycle:
  - `degrade_supply`           (Unknown | Available | Recovering -> Degraded)
  - `mark_supply_unavailable`  (Unknown | Available | Degraded | Recovering -> Unavailable)
  - `mark_supply_recovering`   (Unavailable -> Recovering)
  - `restore_supply`           (Recovering -> Available; recovery acknowledgement)

Lifecycle terminal:
  - `deregister_supply`        (any non-Decommissioned -> Decommissioned)

Method.needs.supplies wire-up is Recipe-side enrichment (no new
slices in this BC).
"""

from cora.supply.features import (
    degrade_supply,
    deregister_supply,
    get_supply,
    list_supplies,
    mark_supply_available,
    mark_supply_recovering,
    mark_supply_unavailable,
    observe_supply_status,
    register_supply,
    restore_supply,
)

__all__ = [
    "degrade_supply",
    "deregister_supply",
    "get_supply",
    "list_supplies",
    "mark_supply_available",
    "mark_supply_recovering",
    "mark_supply_unavailable",
    "observe_supply_status",
    "register_supply",
    "restore_supply",
]
