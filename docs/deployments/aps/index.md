# APS

*Site-level inventories for APS. Aggregates that hang at the facility level: Site Assets, Practices (ISA-88 Site Recipes), facility-issued Clearances, facility-wide Supplies and Cautions.*

| Property | Value |
| --- | --- |
| Level | Site |
| Enterprise | [Argonne](../argonne/index.md) |
| Status | In design |
| Beamlines under this Site | [35-BM](../35-bm/index.md) |

## Inventories

- [Site Assets](site_assets.md): the APS Site Asset and Area Assets under it
- [Practices](practices.md): Practices with `site_id=APS` (ISA-88 Site Recipes)
- [Clearances](clearances.md): APS-issued safety clearances
- [Supplies](supplies.md): facility-wide Supplies (cryogens, beam, shared consumables)
- [Cautions](cautions.md): facility-wide operator Cautions

Source of truth: [`apps/api/tests/integration/test_aps_install_facility_scenario.py`](../../../apps/api/tests/integration/test_aps_install_facility_scenario.py).
