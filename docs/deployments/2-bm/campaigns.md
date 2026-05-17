# Campaigns

*Campaign BC Campaigns registered at 2-BM. A Campaign composes Runs under a coordinated study (proposal-scoped, technique-tagged). See [Model](../../architecture/model.md) for the aggregate shape.*


| Campaign | Shape (`intent` · tags) | Status | Members | Scenario |
| --- | --- | --- | --- | --- |
| `Proposal 2026-1234 beamtime` | `Coordinated` · `proposal`, `tomography`, `porous_media` | `Closed` | 1 Run | `beamtime_intake` (genesis), `tomography_scan` (member added), `data_publish` (start + close) |
| `Proposal 2026-1234 beamtime (degraded)` | `Coordinated` · `proposal`, `tomography`, `porous_media`, `degraded_variant` | `Planned` | 1 Run | `run_debrief_degraded` |
| `Proposal 2026-1234 continuous-rotation series` | `Series` · `proposal`, `continuous_rotation`, `tomography`, `porous_media` | `Planned` | 3 Runs | `continuous_rotation_sweep` |
| `Proposal 2026-1235 beamtime (aborted)` | `Coordinated` · `proposal`, `tomography`, `porous_media`, `aborted_variant` | `Planned` | 1 Run | `run_debrief_aborted` |
| `Proposal 2026-1236 2x2 tile mosaic` | `Coordinated` · `proposal`, `mosaic`, `tomography`, `porous_media` | `Planned` | 4 tile Runs | `mosaic_acquisition` |
| `Proposal 2026-1237 multi-energy contrast study` | `Coordinated` · `proposal`, `tomography`, `multi_energy`, `porous_media` | `Planned` | 2 Runs (distinct Plans) | `energy_change` |

## Pending

Campaign shapes planned for 2-BM but not yet present in the inventory above.

- **Alignment-chain orchestration** — `Coordinated` · `alignment`, `auto_chain`. 5 alignment Runs + calibration + Step-1 re-run.
- **In-situ / operando study** — `Coordinated` · `in_situ`, `operando`.
- **Energy sweep (N-point)** — `Sweep` · `energy_sweep`, `xanes`. (`energy_change` today is a 2-point `Coordinated` pivot, not an N-point `Sweep`.)
- **Block-design experiment** — `Block` · `block_design`.
