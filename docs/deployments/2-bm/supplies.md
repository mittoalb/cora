# Supplies

*Supply BC Supplies at beamline scope. A Supply is a continuously-available resource whose availability the beamline tracks; the 5-state FSM is `Unknown → Available → Degraded → Unavailable → Recovering`. Facility-scope Supplies live at [APS](../aps/supplies.md). See [Model](../../architecture/model.md) for the aggregate shape.*

*See [Scenarios](../../scenarios/index.md) for the operator routines that exercise this surface.*

| Supply | `scope` | `kind` | Lifecycle exercised | Scenario |
| --- | --- | --- | --- | --- |
| `2-BM detector LN2 dewar` | `BEAMLINE` | `cryogen` | `Unknown → Available → Degraded → Unavailable → Recovering → Available` (6-slice walk) | `ln2_dewar_lifecycle` |

Source of truth: [`apps/api/tests/integration/scenarios/test_2bm_ln2_dewar_lifecycle.py`](../../../apps/api/tests/integration/scenarios/test_2bm_ln2_dewar_lifecycle.py).

## Pending in code

| Pending Supply | `scope` | `kind` | Source scenario (planned) |
| --- | --- | --- | --- |
| Sample-environment gas mix | `BEAMLINE` | `gas` | Not yet sourced; lands when a gas-flow Subject environment scenario lands |
| Compressed air supply | `BEAMLINE` | `pneumatic` | Not yet sourced |
