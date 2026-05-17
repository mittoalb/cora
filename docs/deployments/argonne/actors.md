# Actors

*Access BC Actors registered at Argonne. Actors are institutional (not per-beamline); the same Actor can act across any facility, beamline, or BC. See [Model](../../architecture/model.md) for the aggregate shape.*

| Actor | Kind | Role |
| --- | --- | --- |
| `APS Operator` | `human` | Operator principal used by the 35-BM and APS facility scenario tests |
| `Run Debrief` | `agent` | The AI agent co-registered as an Actor by `define_agent` (see [Agents](agents.md)) |

Source of truth: [`apps/api/tests/integration/test_aps_install_facility_scenario.py`](../../../apps/api/tests/integration/test_aps_install_facility_scenario.py) and [`apps/api/tests/integration/test_35bm_beta_alignment_center_scenario.py`](../../../apps/api/tests/integration/test_35bm_beta_alignment_center_scenario.py).

## Pending in code

Real human-operator Actors (per-beamline staff lists, PI rosters, on-call schedules) are not registered. Each lands as a row above when a scenario test or seed script registers it.
