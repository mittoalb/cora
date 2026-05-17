# Clearances

*Safety BC Clearances issued at APS. Each Clearance carries a `kind` (one of 10 facility forms: ESAF, SAF, AForm, DUO, ESRA, ERA, PLHD, DOOR, BTR, Form9) and binds to one or more CORA aggregates or external references. See [Model](../../architecture/model.md) for the aggregate shape.*

| Clearance | `kind` | Bindings | Purpose |
| --- | --- | --- | --- |
| `APS scenario ESAF (facility umbrella)` | `ESAF` | APS Site Asset | Umbrella ESAF used by scenario tests; binds to the APS Site Asset rather than a specific Subject or Run |

Source of truth: [`apps/api/tests/integration/scenarios/test_aps_facility.py`](../../../apps/api/tests/integration/scenarios/test_aps_facility.py).

## Pending in code

Real APS-issued ESAFs (per-experiment, per-proposal) and other clearance kinds (SAF for synchrotron access, DOOR for door interlocks) are not yet registered. Each lands as a row above when a scenario test or seed script registers it.
