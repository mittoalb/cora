# Subjects

*Subject BC Subjects registered at 2-BM. A Subject is the sample-or-thing being measured (proposal-anchored at operations phase, kinematic-mounted at acquisition time). See [Model](../../architecture/model.md) for the aggregate shape.*

| Subject | Class | Proposal | Most-advanced state |
| --- | --- | --- | --- |
| `porous sandstone core (Proposal 2026-1234, sample A)` | porous-media core (sandstone) | `2026-1234` | `Received` (post-dismount; full cycle Received -> Mounted -> Measured -> Received exercised) |
| `porous sandstone core (Proposal 2026-1234, sample A, continuous rotation)` | porous-media core (sandstone) | `2026-1234` | `Measured` (single mount across N=3 back-to-back rotation Runs under a Series Campaign) |
| `porous sandstone core (Proposal 2026-1234, sample A, degraded run)` | porous-media core (sandstone) | `2026-1234` | `Mounted` (degraded-completion Run scenario; debrief variant) |
| `porous sandstone core (Proposal 2026-1235, sample B, aborted run)` | porous-media core (sandstone) | `2026-1235` | `Mounted` (EquipmentAbort Run scenario; debrief variant) |
| `wide sandstone slab (Proposal 2026-1236, mosaic acquisition)` | porous-media slab (sandstone) | `2026-1236` | `Measured` (single mount across N=4 tile Runs under a Coordinated Campaign) |
| `iron-bearing sandstone core (Proposal 2026-1237, energy-pivot study)` | porous-media core (sandstone) | `2026-1237` | `Measured` (single mount across two Runs on distinct low/high-energy Plans under a Coordinated Campaign) |

Source of truth: [`apps/api/tests/integration/scenarios/test_2bm_beamtime_intake.py`](../../../apps/api/tests/integration/scenarios/test_2bm_beamtime_intake.py) (Received genesis), [`apps/api/tests/integration/scenarios/test_2bm_mount_sample.py`](../../../apps/api/tests/integration/scenarios/test_2bm_mount_sample.py) (Received -> Mounted), [`apps/api/tests/integration/scenarios/test_2bm_tomography_scan.py`](../../../apps/api/tests/integration/scenarios/test_2bm_tomography_scan.py) (Mounted -> Measured), [`apps/api/tests/integration/scenarios/test_2bm_dismount_sample.py`](../../../apps/api/tests/integration/scenarios/test_2bm_dismount_sample.py) (Measured -> Received), [`apps/api/tests/integration/scenarios/test_2bm_continuous_rotation_sweep.py`](../../../apps/api/tests/integration/scenarios/test_2bm_continuous_rotation_sweep.py) (shared Subject across N Series Runs), [`apps/api/tests/integration/scenarios/test_2bm_run_debrief_degraded.py`](../../../apps/api/tests/integration/scenarios/test_2bm_run_debrief_degraded.py) (debrief on Degraded), [`apps/api/tests/integration/scenarios/test_2bm_run_debrief_aborted.py`](../../../apps/api/tests/integration/scenarios/test_2bm_run_debrief_aborted.py) (debrief on EquipmentAbort), [`apps/api/tests/integration/scenarios/test_2bm_mosaic_acquisition.py`](../../../apps/api/tests/integration/scenarios/test_2bm_mosaic_acquisition.py) (shared Subject across mosaic tiles), [`apps/api/tests/integration/scenarios/test_2bm_energy_change.py`](../../../apps/api/tests/integration/scenarios/test_2bm_energy_change.py) (shared Subject across energy pivot).

The Subject's lifecycle (`Received -> Mounted -> Measured -> Received`) is exercised across operations-phase scenarios; the "Most-advanced state" column reflects the furthest state any shipped scenario reaches. Subjects-page row lands here once per logical sample (same Subject by name; each scenario isolates UUIDs via the per-test template DB).

## Pending in code

The following Subjects are surfaced by the [2-BM repo survey](https://github.com/xray-imaging/2bm-docs) but not yet registered in code. Each materializes as a row above when its scenario test (or a seed script) registers it.

| Pending Subject | Class | Source scenario (planned) |
| --- | --- | --- |
| Subject disposition (Returned / Stored / Discarded terminals) | Terminal lifecycle states after dismount | Not yet sourced; sibling slices `return_subject` / `store_subject` / `discard_subject` would each get their own scenario when the disposition policy is locked |
| Proposal co-I sample roster | Multi-sample-class per proposal | `tests/integration/scenarios/test_2bm_beamtime_intake.py` (extension: `dmagic` pulls proposal metadata + tags TomoScan IOC; PI + co-Is registered as Actors, samples as Subjects) |
| Calibration phantom (Siemens star, USAF 1951, sphere) | Calibration-class Subject (kinematic-mounted, no proposal) | Not yet sourced as its own scenario; the alignment scenarios use sphere fixtures inline today without registering them as Subjects |

The Subject BC supports `Mounted -> Measured -> Received` lifecycle (per [Subject mount alignment design](../../architecture/model.md)); operations-phase scenarios will exercise the full cycle. Beamline `index.md` notes the lifecycle facets to be exercised per scenario.
