# Assets

*Equipment BC Assets registered **under** the APS Site (the Sectors at the Area level). The APS Asset itself sits at the Site level and is declared on the [APS index](index.md). See [Model](../../architecture/model.md) for the aggregate shape.*

| Asset | Level | Parent | Hosts |
| --- | --- | --- | --- |
| `Sector 2` | `Area` | `APS` (Site) | [2-BM](../2-bm/index.md) Unit |

Source of truth: [`apps/api/tests/integration/scenarios/test_aps_facility.py`](../../../apps/api/tests/integration/scenarios/test_aps_facility.py).

## Pending in code

- `Sector 35`: lands when the [35-BM](../35-bm/index.md) Unit is registered.
- Other Sectors and shared facility equipment (storage ring, beam transport, front-end optics) are not modelled until a pilot demands them per [Pilots earn the abstractions](../index.md).
