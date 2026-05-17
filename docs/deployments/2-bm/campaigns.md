# Campaigns

*Campaign BC Campaigns registered at 2-BM. A Campaign composes Runs under a coordinated study (proposal-scoped, technique-tagged). See [Model](../../architecture/model.md) for the aggregate shape.*

*See [Scenarios](../../scenarios/index.md) for the operator routines that exercise this surface.*

| Campaign | `intent` | Tags | Status | Members | Scenario |
| --- | --- | --- | --- | --- | --- |
| `Proposal 2026-1234 beamtime` | `Coordinated` | `proposal`, `tomography`, `porous_media` | `Closed` | 1 Run | `beamtime_intake` (genesis), `tomography_scan` (member added), `data_publish` (start + close) |
| `Proposal 2026-1234 beamtime (degraded)` | `Coordinated` | `proposal`, `tomography`, `porous_media`, `degraded_variant` | `Planned` | 1 Run | `run_debrief_degraded` |
| `Proposal 2026-1234 continuous-rotation series` | `Series` | `proposal`, `continuous_rotation`, `tomography`, `porous_media` | `Planned` | 3 Runs | `continuous_rotation_sweep` |
| `Proposal 2026-1235 beamtime (aborted)` | `Coordinated` | `proposal`, `tomography`, `porous_media`, `aborted_variant` | `Planned` | 1 Run | `run_debrief_aborted` |
| `Proposal 2026-1236 2x2 tile mosaic` | `Coordinated` | `proposal`, `mosaic`, `tomography`, `porous_media` | `Planned` | 4 tile Runs | `mosaic_acquisition` |
| `Proposal 2026-1237 multi-energy contrast study` | `Coordinated` | `proposal`, `tomography`, `multi_energy`, `porous_media` | `Planned` | 2 Runs (distinct Plans) | `energy_change` |

Source of truth: scenario files at [`apps/api/tests/integration/scenarios/test_2bm_<scenario>.py`](../../../apps/api/tests/integration/scenarios/) (one-to-one with the Scenario column). FSM coverage: `Planned → Active → Closed` exercised by the `data_publish` path; `Held` and `Abandoned` not yet exercised.

## Pending in code

| Pending Campaign | `intent` | Tags | Source scenario (planned) |
| --- | --- | --- | --- |
| Alignment-chain orchestration | `Coordinated` | `alignment`, `auto_chain` | `test_2bm_alignment_auto_chain.py` (5 alignment Runs + calibration + Step-1 re-run) |
| In-situ / operando study | `Coordinated` | `in_situ`, `operando` | Not yet sourced |
| Energy sweep (N-point) | `Sweep` | `energy_sweep`, `xanes` | Not yet sourced (`energy_change` is a 2-point `Coordinated` pivot, not an N-point `Sweep`) |
| Block-design experiment | `Block` | `block_design` | Not yet sourced |
