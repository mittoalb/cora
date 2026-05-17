# Assets

*Equipment BC Assets registered **under** the Argonne Enterprise (the Sites that hang off it). The Argonne Asset itself sits at the top of the hierarchy and is declared on the [Argonne index](index.md). See [Model](../../architecture/model.md) for the aggregate shape.*

| Asset | Level | Parent |
| --- | --- | --- |
| `APS` | `Site` | `Argonne` (Enterprise) |

Source of truth: [`apps/api/tests/integration/scenarios/test_aps_facility.py`](../../../apps/api/tests/integration/scenarios/test_aps_facility.py).

## Pending in code

Other Argonne sibling Sites (ATLAS, CNM, ALCF, ...) are not registered. They land here when a pilot demands them per [Pilots earn the abstractions](../index.md).
