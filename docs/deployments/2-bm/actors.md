# Actors

*Access BC Actors registered at 2-BM by the beamline install ceremony, the canonical beamtime fixture, and per-scenario intake. These are beamline-bound principals: staff on the 2-BM rota, proposal PIs tied to a beamtime, and review-chain reviewers whose first registration lives in a 2-BM scenario. Facility-wide principals (the APS Operator role, the Run Debrief agent) live at [APS](../aps/actors.md). See [Model](../../architecture/model.md) for the aggregate shape.*

*See [Scenarios](../../scenarios/index.md) for the operator routines that exercise this surface.*

| Actor | Kind | Role |
| --- | --- | --- |
| `2-BM Operator 1` | `human` | 2-BM beamline staff (pool position 1); registered by `install_aps_unit` and assigned to scenarios via `operator_for(__file__)` (round-robin by `blake2b` of the test filename) |
| `2-BM Operator 2` | `human` | 2-BM beamline staff (pool position 2); same registration and assignment as Operator 1 |
| `2-BM Operator 3` | `human` | 2-BM beamline staff (pool position 3); same registration and assignment as Operator 1 |
| `Proposal 2026-1234 PI` | `human` | Proposal PI for the canonical proposal-2026-1234 beamtime; registered by `open_beamtime()` (the canonical beamtime fixture, used by 12+ scenarios) |
| `Proposal 2026-1235 PI` | `human` | Proposal PI for the aborted-variant beamtime in `test_2bm_run_debrief_aborted.py` |
| `Proposal 2026-1236 PI` | `human` | Proposal PI for the Coordinated mosaic beamtime in `test_2bm_mosaic_acquisition.py` |
| `Proposal 2026-1237 PI` | `human` | Proposal PI for the multi-energy beamtime in `test_2bm_energy_change.py` |
| `Sample-of-opportunity PI` | `human` | Proposal PI for the early-stop scan in `test_2bm_run_stopped_early.py` |
| `2-BM Beamline Scientist` | `human` | Review-chain reviewer for the proposal-Clearance workflow; first registration in `test_2bm_proposal_clearance.py` |
| `APS Experiment Safety Review Board` | `human` | Review-chain reviewer (ESRB) for the proposal-Clearance workflow; first registration in `test_2bm_proposal_clearance.py` (the Actor name carries APS scope but the registration ceremony lives at 2-BM today; see Promotion triggers below) |
| `2-BM Beamline Scientist + ESRB Reviewer` | `human` | Combined-role reviewer for scenarios that compress the two-step review chain; first registration in `test_2bm_run_start_gated_by_clearance.py` |

Source of truth: [`_facility_fixture.py`](../../../apps/api/tests/integration/scenarios/_facility_fixture.py) (operator pool + `operator_for` round-robin), [`_beamtime_fixture.py`](../../../apps/api/tests/integration/scenarios/_beamtime_fixture.py) (`open_beamtime()` registers the PI from `BeamtimeSpec.pi_actor_name`), [`test_2bm_beamtime_intake.py`](../../../apps/api/tests/integration/scenarios/test_2bm_beamtime_intake.py), [`test_2bm_mount_sample.py`](../../../apps/api/tests/integration/scenarios/test_2bm_mount_sample.py), [`test_2bm_proposal_clearance.py`](../../../apps/api/tests/integration/scenarios/test_2bm_proposal_clearance.py), [`test_2bm_run_start_gated_by_clearance.py`](../../../apps/api/tests/integration/scenarios/test_2bm_run_start_gated_by_clearance.py).

## Promotion triggers

When a row moves from 2-BM Actors to [APS Actors](../aps/actors.md):

- **PI**: a non-2-BM beamline scenario references the same `Actor.id` (instead of registering a fresh PI).
- **ESRB**: a second beamline scenario references `_ESRB_ACTOR_ID` (or any ESRB Actor). The ESRB registration then hoists into [`test_aps_facility.py`](../../../apps/api/tests/integration/scenarios/test_aps_facility.py).
- **Beamline Scientist**: stays at 2-BM unless a sibling-beamline Beamline Scientist Actor is registered with the same id.

## Pending in code

- Per-beamline named staff rosters (real individuals, on-call schedules) beyond the 3-operator pool and the review-chain reviewers above.
- Sibling proposal PI rosters for proposals that have not yet been exercised by a scenario.
- The combined-role `2-BM Beamline Scientist + ESRB Reviewer` is a test-scenario convenience; it will likely be replaced by separate Beamline Scientist + ESRB references once the clearance workflow is exercised by more scenarios.
