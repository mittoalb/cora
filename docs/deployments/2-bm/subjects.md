# Subjects

*Subject BC Subjects registered at 2-BM. A Subject is the sample-or-thing being measured (proposal-anchored at operations phase, kinematic-mounted at acquisition time). See [Model](../../architecture/model.md) for the aggregate shape.*


| Subject | Class | Proposal | Most-advanced state | Scenario(s) |
| --- | --- | --- | --- | --- |
| `porous sandstone core (Proposal 2026-1234, sample A)` | porous-media core (sandstone) | `2026-1234` | `Received` (full `Received → Mounted → Measured → Received` cycle) | `beamtime_intake`, `mount_sample`, `tomography_scan`, `dismount_sample` |
| `porous sandstone core (Proposal 2026-1234, sample A, continuous rotation)` | porous-media core (sandstone) | `2026-1234` | `Measured` (single mount across N=3 Series Runs) | `continuous_rotation_sweep` |
| `porous sandstone core (Proposal 2026-1234, sample A, degraded run)` | porous-media core (sandstone) | `2026-1234` | `Mounted` | `run_debrief_degraded` |
| `porous sandstone core (Proposal 2026-1234, sample A, with readings)` | porous-media core (sandstone) | `2026-1234` | `Mounted` | `run_reading_logbook` |
| `porous sandstone core (Proposal 2026-1234, sample A, beam-trip pause)` | porous-media core (sandstone) | `2026-1234` | `Mounted` | `run_hold_resume_cycle` |
| `porous sandstone core (Proposal 2026-1234, sample A, overnight outage)` | porous-media core (sandstone) | `2026-1234` | `Mounted` | `run_truncated_after_outage` |
| `porous sandstone core (Proposal 2026-1235, sample B, aborted run)` | porous-media core (sandstone) | `2026-1235` | `Mounted` | `run_debrief_aborted` |
| `leftover sandstone core (sample-of-opportunity)` | porous-media core (sandstone) | (none, sample-of-opportunity) | `Mounted` | `run_stopped_early` |
| `wide sandstone slab (Proposal 2026-1236, mosaic acquisition)` | porous-media slab (sandstone) | `2026-1236` | `Measured` (single mount across N=4 mosaic tiles) | `mosaic_acquisition` |
| `iron-bearing sandstone core (Proposal 2026-1237, energy-pivot study)` | porous-media core (sandstone) | `2026-1237` | `Measured` (single mount across two Plans) | `energy_change` |

## Pending

Subject shapes planned for 2-BM but not yet present in the inventory above.

- **Subject disposition terminals** (`Returned` / `Stored` / `Discarded`) — sibling slices `return_subject` / `store_subject` / `discard_subject`, each landing when the disposition policy is locked.
- **Proposal co-I sample roster** — multi-sample-class per proposal (`dmagic` metadata + TomoScan IOC tagging).
- **Calibration phantom** (Siemens star, USAF 1951, sphere) — calibration-class Subject (no proposal); alignment scenarios use sphere fixtures inline today.
