# Site Assets

*Equipment BC Assets registered at the APS Site level (and Area levels below it). See [Model](../../architecture/model.md) for the aggregate shape.*

| Asset | Level | Parent |
| --- | --- | --- |
| `APS` | `Site` | `Argonne` (Enterprise) |

Source of truth: [`apps/api/tests/integration/test_aps_install_facility_scenario.py`](../../../apps/api/tests/integration/test_aps_install_facility_scenario.py).

## Pending in code

Area-level Assets under APS (the experimental halls, sectors, beamline-cluster groupings) and shared facility equipment (storage ring, beam transport, front-end optics) are not yet registered. Each lands as a row above when a scenario test or seed script instantiates it.
