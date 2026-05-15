"""Vertical slices for the Supply BC.

Phase 10a-a ships:
  - `register_supply`        (genesis -> Unknown; create-style)
  - `mark_supply_available`  (Unknown -> Available; operator first observation)
  - `get_supply`             (read side; lands in iter 3)
  - `list_supplies`          (read side; lands in iter 3)

Phase 10a-b adds the degradation/recovery cycle:
  - `degrade_supply`           (Unknown | Available | Recovering -> Degraded)
  - `mark_supply_unavailable`  (Unknown | Available | Degraded | Recovering -> Unavailable)
  - `mark_supply_recovering`   (Unavailable -> Recovering)
  - `restore_supply`           (Recovering -> Available; recovery acknowledgement)

Phase 10b adds Method.needs.supplies wire-up (Recipe-side enrichment;
no new slices in this BC).
"""

from cora.supply.features import mark_supply_available, register_supply

__all__ = [
    "mark_supply_available",
    "register_supply",
]
