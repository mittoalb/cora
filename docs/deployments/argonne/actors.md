# Actors

*Access BC Actors registered at Argonne. Actors are institutional principals (facility-wide identity), not per-scenario. The 2-BM scenario corpus shares a small pool of beamline-operator principals so the same operator drives multiple scenarios, mirroring how real beamline staff work across shifts. See [Model](../../architecture/model.md) for the aggregate shape.*

| Actor | Kind | Role |
| --- | --- | --- |
| `APS Operator` | `human` | Facility-level operator principal registered by the canonical `test_aps_facility.py` install ceremony |
| `2-BM Operator 1` | `human` | 2-BM beamline staff (pool position 1); registered by the canonical `install_aps_unit` fixture and assigned to scenarios by round-robin filename hash |
| `2-BM Operator 2` | `human` | 2-BM beamline staff (pool position 2); same registration and assignment as Operator 1 |
| `2-BM Operator 3` | `human` | 2-BM beamline staff (pool position 3); same registration and assignment as Operator 1 |
| `Run Debrief` | `agent` | The AI agent co-registered as an Actor by `define_agent` at facility scope (see [Agents](agents.md)); canonical UUID shared with the [2-BM Agent Policy](../2-bm/policies.md) |
| `Dr. PI (Proposal 2026-1234 lead)` | `human` | Proposal PI; Campaign lead for the canonical proposal-2026-1234 beamtime; registered by the operator (acting on PI's behalf) during `beamtime_intake` |

Source of truth: [`apps/api/tests/integration/scenarios/test_aps_facility.py`](../../../apps/api/tests/integration/scenarios/test_aps_facility.py) (APS Operator + Run Debrief agent), [`apps/api/tests/integration/scenarios/_facility_fixture.py`](../../../apps/api/tests/integration/scenarios/_facility_fixture.py) (the 3-operator pool + canonical UUIDs), [`apps/api/tests/integration/scenarios/test_2bm_beamtime_intake.py`](../../../apps/api/tests/integration/scenarios/test_2bm_beamtime_intake.py) (PI).

## Why a 3-operator pool

Real beamlines are staffed by 1-3 people who rotate across shifts and routines. The same operator who runs cold-start motor-homing in the morning might also run a tomography scan in the afternoon. Modelling each scenario's principal as a fresh per-scenario Actor was a test-corpus artefact (hermeticity convenience) that contradicted that reality and made cross-scenario `actor_id` references meaningless. The pool collapses that: every 2-BM scenario picks one of three canonical UUIDs via `operator_for(__file__)`, so the same Operator id appears across multiple scenarios exactly as a real human would.

The operator pool is human-only by definition. Agents (the `Run Debrief` AI) are also Access BC Actors but they are not interchangeable like operators are; each agent has a specific role. The Trust-side permissions for the two groups live in separate [Policies](../2-bm/policies.md).

## Pending in code

Per-beamline named staff rosters (real individuals, on-call schedules) and additional proposal PI rosters beyond the first canonical PI are not yet registered. When they land they will be additional rows above, not replacements for the pool.
