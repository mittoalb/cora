# Argonne

*Enterprise-level inventories. Aggregates that hang at the institution level (Actors, Agents) and the root Asset of CORA's Equipment hierarchy.*

| Property | Value |
| --- | --- |
| Asset | `Argonne` (Enterprise, root) |
| Status | Operational |
| Sites under this Enterprise | [APS](../aps/index.md) |

## Inventories

What's registered under Argonne today:

- [Assets](assets.md): sibling Sites under the Argonne Enterprise (APS is the only one registered; ATLAS / CNM / ALCF are not modelled until a pilot demands them)
- [Actors](actors.md): human Actors registered at Argonne
- [Agents](agents.md): AI Agents registered at Argonne

Source of truth: [`apps/api/tests/integration/scenarios/test_aps_facility.py`](../../../apps/api/tests/integration/scenarios/test_aps_facility.py).
