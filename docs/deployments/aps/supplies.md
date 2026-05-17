# Supplies

*Supply BC Supplies at facility scope. A Supply is a continuously-available resource whose availability the facility tracks. See [Model](../../architecture/model.md) for the aggregate shape.*

| Supply | `scope` | `kind` | Initial status |
| --- | --- | --- | --- |
| `APS liquid helium` | `Facility` | `cryogen` | `Unknown` (lands here; transitions to `Available` via `mark_supply_available`) |

Source of truth: [`apps/api/tests/integration/test_aps_install_facility_scenario.py`](../../../apps/api/tests/integration/test_aps_install_facility_scenario.py).

## Pending in code

Other facility-wide Supplies (storage-ring beam current, liquid nitrogen, gas mixtures for sample environments) are not yet registered. Each lands as a row above when a scenario test or seed script registers it.
