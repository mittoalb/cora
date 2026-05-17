# Actors

*Access BC Actors registered at Argonne. Actors are institutional (not per-beamline); the same Actor can act across any facility, beamline, or BC. See [Model](../../architecture/model.md) for the aggregate shape.*

| Actor | Kind | Role |
| --- | --- | --- |
| `APS Operator` | `human` | Operator principal used by the 2-BM and APS facility scenario tests |
| `Run Debrief` | `agent` | The AI agent co-registered as an Actor by `define_agent` (see [Agents](agents.md)) |
| `Dr. PI (Proposal 2026-1234 lead)` | `human` | Proposal PI; Campaign lead for the first canonical operations-phase beamtime; registered by the operator (acting on PI's behalf) during `beamtime_intake` |

Source of truth: [`apps/api/tests/integration/scenarios/test_aps_facility.py`](../../../apps/api/tests/integration/scenarios/test_aps_facility.py), [`apps/api/tests/integration/scenarios/test_2bm_alignment_center.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_center.py), [`apps/api/tests/integration/scenarios/test_2bm_beamtime_intake.py`](../../../apps/api/tests/integration/scenarios/test_2bm_beamtime_intake.py).

## Pending in code

Real human-operator Actors (per-beamline staff lists, on-call schedules) and additional proposal PI rosters are not yet registered beyond the first canonical PI. Each lands as a row above when a scenario test or seed script registers it.
