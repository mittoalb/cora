# Runs

*Run BC Runs registered at 2-BM. A Run is the operator-started execution of a Plan against a Subject, lifecycle `Created → Running → (Completed | Aborted | Stopped | Truncated)`. Runs are composed by [Campaigns](campaigns.md) (`Run.campaign_id ↔ Campaign.run_ids`) and produce [Datasets](datasets.md) (`Dataset.producing_run_id`). See [Model](../../architecture/model.md) for the aggregate shape.*

*See [Scenarios](../../scenarios/index.md) for the operator routines that exercise this surface.*

| Run | Subject | Campaign | Terminal state | Scenario |
| --- | --- | --- | --- | --- |
| `Proposal 2026-1234 sample A tomography (first proposal scan)` | [`porous sandstone core (Proposal 2026-1234, sample A)`](subjects.md) | [`Proposal 2026-1234 beamtime`](campaigns.md) | `Completed` | `tomography_scan` |
| `Proposal 2026-1234 sample A tomography` | `porous sandstone core (Proposal 2026-1234, sample A)` | `Proposal 2026-1234 beamtime` | `Completed` (Dataset promoted) | `data_publish` |
| `Proposal 2026-1234 sample A tomography (with reading logbook)` | `porous sandstone core (Proposal 2026-1234, sample A, with readings)` | `Proposal 2026-1234 beamtime (with readings)` | `Completed` (RunReading entries appended baseline + monitor) | `run_reading_logbook` |
| `Proposal 2026-1234 sample A tomography (with beam-trip pause)` | `porous sandstone core (Proposal 2026-1234, sample A, beam-trip pause)` | `Proposal 2026-1234 beamtime (with mid-flight pause)` | `Completed` (Hold → Resume mid-flight) | `run_hold_resume_cycle` |
| `Proposal 2026-1234 sample A overnight tomography` | `porous sandstone core (Proposal 2026-1234, sample A, overnight outage)` | `Proposal 2026-1234 beamtime (outage truncated)` | `Truncated` (operations-floor power outage) | `run_truncated_after_outage` |
| `Proposal 2026-1234 sample A streaming tomography` | `porous sandstone core (Proposal 2026-1234, sample A)` | `Proposal 2026-1234 beamtime` | `Completed` (mid-flight `adjust_run`) | `streaming_tomography` |
| `Proposal 2026-1234 sample A tomography (with intervention)` | `porous sandstone core (Proposal 2026-1234, sample A, degraded run)` | `Proposal 2026-1234 beamtime (degraded)` | `Completed`, debriefed `DegradedCompletion` (Hexapod degrade/restore) | `run_debrief_degraded` |
| `Proposal 2026-1235 sample B tomography (aborted on hexapod fault)` | `porous sandstone core (Proposal 2026-1235, sample B, aborted run)` | `Proposal 2026-1235 beamtime (aborted)` | `Aborted`, debriefed `EquipmentAbort` | `run_debrief_aborted` |
| `Sample-of-opportunity tomography (planning 1500 projections)` | `leftover sandstone core (sample-of-opportunity)` | `Sample-of-opportunity scan (early-stop)` | `Stopped` (live-reco saturated; partial Dataset registered) | `run_stopped_early` |
| `mosaic tile {0..3}` (N=4) | [`wide sandstone slab (Proposal 2026-1236, mosaic acquisition)`](subjects.md) | [`Proposal 2026-1236 2x2 tile mosaic`](campaigns.md) | `Completed` (each tile) | `mosaic_acquisition` |
| `continuous-rotation child Run {1..3}/3` (N=3) | `porous sandstone core (Proposal 2026-1234, sample A, continuous rotation)` | [`Proposal 2026-1234 continuous-rotation series`](campaigns.md) | `Completed` (each child) | `continuous_rotation_sweep` |
| `Proposal 2026-1237 low-energy tomography (25 keV)` | `iron-bearing sandstone core (Proposal 2026-1237, energy-pivot study)` | [`Proposal 2026-1237 multi-energy contrast study`](campaigns.md) | `Completed` | `energy_change` |
| `Proposal 2026-1237 high-energy tomography (30 keV)` | `iron-bearing sandstone core (Proposal 2026-1237, energy-pivot study)` | `Proposal 2026-1237 multi-energy contrast study` | `Completed` (operator-authored `EnergyChange` [Decision](decisions.md) between Plans) | `energy_change` |

Source of truth: scenario files at [`apps/api/tests/integration/scenarios/test_2bm_<scenario>.py`](../../../apps/api/tests/integration/scenarios/) (one-to-one with the Scenario column).

## Lifecycle facets exercised

| Facet | Scenario(s) |
| --- | --- |
| Terminal `Completed` | `tomography_scan`, `data_publish`, `streaming_tomography`, `mosaic_acquisition` (N=4), `continuous_rotation_sweep` (N=3), `energy_change` (N=2), `run_debrief`, `run_debrief_degraded` |
| Terminal `Aborted` (Equipment fault) | `run_debrief_aborted` |
| Terminal `Aborted` (Operator decision, no fault) | Pending (variant of `run_debrief_aborted` distinguished by reason) |
| Terminal `Stopped` (operator-issued stop with partial-data valid) | `run_stopped_early` |
| Terminal `Truncated` (early termination, partial-data accepted) | `run_truncated_after_outage` |
| Mid-flight `Hold → Resume` | `run_hold_resume_cycle` |
| Mid-flight `adjust_run` (parameter steering) | `streaming_tomography` |
| Mid-flight degrade/restore on a target Asset | `run_debrief_degraded` (Hexapod degrade → recover → continue → Complete) |
| `RunReading` logbook appended (`baseline` + `monitor` sampling procedures) | `run_reading_logbook` |
| Run member of a Coordinated Campaign | `tomography_scan`, `mosaic_acquisition`, `energy_change` |
| Run member of a Series Campaign | `continuous_rotation_sweep` |
| Run with no Campaign membership | Not exercised (every shipped Run is Campaign-bound today) |

## Pending in code

| Pending Run shape | Source scenario (planned) |
| --- | --- |
| `Aborted` via operator decision (vs Equipment fault) | Variant of `run_debrief_aborted` distinguished only by abort reason |
| Alignment-chain Runs composed into one Campaign | `test_2bm_alignment_auto_chain.py` (5 alignment Runs + calibration + a Step-1 re-run under a Coordinated Campaign) |
| Energy-calibration Run (rocking-curve) | `test_2bm_energy_calibration.py` (channel-cut-crystal scan; produces a rocking-curve [Dataset](datasets.md)) |
| Vibration-baseline Run (1000-frame high-speed) | `test_2bm_vibration_baseline.py` (pre / post air-handler shutdown comparison) |
