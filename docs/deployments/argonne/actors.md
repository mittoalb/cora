# Actors

*Access BC Actors registered at Argonne. Actors are institutional (not per-beamline); the same Actor can act across any facility, beamline, or BC. See [Model](../../architecture/model.md) for the aggregate shape.*

| Actor | Kind | Role |
| --- | --- | --- |
| `APS Operator` | `human` | Operator principal used by the 2-BM and APS facility scenario tests |
| `Run Debrief` | `agent` | The AI agent co-registered as an Actor by `define_agent` (see [Agents](agents.md)) |

Source of truth: [`apps/api/tests/integration/scenarios/test_aps_facility.py`](../../../apps/api/tests/integration/scenarios/test_aps_facility.py) and [`apps/api/tests/integration/scenarios/test_2bm_alignment_center.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_center.py).

## Pending in code

Real human-operator Actors (per-beamline staff lists, PI rosters, on-call schedules) are not registered. Each lands as a row above when a scenario test or seed script registers it.
