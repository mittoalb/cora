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

For which scenarios exercise each lifecycle facet (terminal states, mid-flight transitions, Campaign membership shapes), see [Scenarios > by-bc > Run](../../scenarios/by-bc.md#run).

## Pending

Run shapes planned for 2-BM but not yet present in the inventory above.

- **`Aborted` via operator decision** (vs Equipment fault) — distinct from the existing `EquipmentAbort` Run by abort reason.
- **Alignment-chain Runs composed into one Campaign** — 5 alignment Runs + calibration + a Step-1 re-run under a Coordinated Campaign.
- **Energy-calibration Run** (channel-cut-crystal rocking-curve) — produces a rocking-curve [Dataset](datasets.md).
- **Vibration-baseline Run** (1000-frame high-speed) — pre / post air-handler shutdown comparison.
