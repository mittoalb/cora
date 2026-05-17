# Argonne

*Enterprise-level inventories. The root of CORA's Equipment hierarchy and the holding parent for the Sites that hang off it.*

| Property | Value |
| --- | --- |
| Asset | `Argonne` (Enterprise, root) |
| Status | Operational |
| Sites under this Enterprise | [APS](../aps/index.md) |

## Inventories

- [Assets](assets.md): sibling Sites under the Argonne Enterprise (APS is the only one registered).

No Actors / Agents inventoried: Argonne has no install ceremony of its own, so no principal is registered at Enterprise scope today. Identity registration begins at the [APS](../aps/index.md) Site (facility-wide) and continues at each beamline. A row lands here when a cross-Site principal is registered (one that spans APS and a sibling Site such as ATLAS).

Source of truth: [`test_aps_facility.py`](../../../apps/api/tests/integration/scenarios/test_aps_facility.py) (creates the Argonne Enterprise Asset as the root of the Site hierarchy at [line 159](../../../apps/api/tests/integration/scenarios/test_aps_facility.py#L159)).
