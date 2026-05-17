# APS

*Site-level inventories for APS. Aggregates that hang at the facility level: Assets, Practices (ISA-88 Site Recipes), facility-issued Clearances, facility-wide Supplies and Cautions.*

| Property | Value |
| --- | --- |
| Asset | `APS` (Site, parent `Argonne`) |
| Enterprise | [Argonne](../argonne/index.md) |
| Status | Operational |
| Sectors under this Site | `Sector 2` (registered); `Sector 35` (pending, lands with 35-BM) |
| Beamlines under this Site | [2-BM](../2-bm/index.md) under `Sector 2` (Operational); [35-BM](../35-bm/index.md) under `Sector 35` (Planned) |

APS organises beamlines into sectors. Each sector is an `Area`-level Asset between the `APS` Site and the beamline `Unit`. Beamlines do **not** parent directly to APS.

## Inventories

- [Assets](assets.md): Area Assets under APS (the Sectors)
- [Practices](practices.md): Practices with `site_id=APS` (ISA-88 Site Recipes)
- [Clearances](clearances.md): APS-issued safety clearances
- [Supplies](supplies.md): facility-wide Supplies (cryogens, beam, shared consumables)
- [Cautions](cautions.md): facility-wide operator Cautions

Source of truth: [`apps/api/tests/integration/scenarios/test_aps_facility.py`](../../../apps/api/tests/integration/scenarios/test_aps_facility.py).
