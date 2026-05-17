# Subjects

*Subject BC Subjects registered at 2-BM. A Subject is the sample-or-thing being measured (proposal-anchored at operations phase, kinematic-mounted at acquisition time). See [Model](../../architecture/model.md) for the aggregate shape.*

| Subject | Class | Proposal | Most-advanced state |
| --- | --- | --- | --- |
| `porous sandstone core (Proposal 2026-1234, sample A)` | porous-media core (sandstone) | `2026-1234` | `Mounted` (on `Aerotech_ABRS_rotary`) |

Source of truth: [`apps/api/tests/integration/scenarios/test_2bm_beamtime_intake.py`](../../../apps/api/tests/integration/scenarios/test_2bm_beamtime_intake.py) (Received genesis), [`apps/api/tests/integration/scenarios/test_2bm_mount_sample.py`](../../../apps/api/tests/integration/scenarios/test_2bm_mount_sample.py) (Received -> Mounted transition).

The Subject's lifecycle (`Received -> Mounted -> Measured -> Received`) is exercised across operations-phase scenarios; the "Most-advanced state" column reflects the furthest state any shipped scenario reaches. Subjects-page row lands here once per logical sample (same Subject by name; each scenario isolates UUIDs via the per-test template DB).

## Pending in code

The following Subjects are surfaced by the [2-BM repo survey](https://github.com/xray-imaging/2bm-docs) but not yet registered in code. Each materializes as a row above when its scenario test (or a seed script) registers it.

| Pending Subject | Class | Source scenario (planned) |
| --- | --- | --- |
| Measured sandstone core (post-scan lifecycle transition) | Same Subject as above, advanced to `Measured` | `tests/integration/scenarios/test_2bm_tomography_scan.py` (Phase O-3: scan Run transitions Subject `Mounted -> Measured`) |
| Returned-to-storage sandstone core (post-dismount) | Same Subject as above, back to `Received` | `tests/integration/scenarios/test_2bm_dismount_sample.py` (Phase O-5: Subject lifecycle `Measured -> Received`) |
| Proposal co-I sample roster | Multi-sample-class per proposal | `tests/integration/scenarios/test_2bm_beamtime_intake.py` (extension: `dmagic` pulls proposal metadata + tags TomoScan IOC; PI + co-Is registered as Actors, samples as Subjects) |
| Mosaic-acquisition shared Subject | Single Subject under Campaign(intent=Coordinated) | `tests/integration/scenarios/test_2bm_mosaic_acquisition.py` (N tiled scans share one Subject) |
| Continuous-rotation shared Subject | Single Subject under Campaign(intent=Series) | `tests/integration/scenarios/test_2bm_continuous_rotation_sweep.py` (N back-to-back acquisitions on one mounted sample) |
| Calibration phantom (Siemens star, USAF 1951, sphere) | Calibration-class Subject (kinematic-mounted, no proposal) | Not yet sourced as its own scenario; the alignment scenarios use sphere fixtures inline today without registering them as Subjects |

The Subject BC supports `Mounted -> Measured -> Received` lifecycle (per [Subject mount alignment design](../../architecture/model.md)); operations-phase scenarios will exercise the full cycle. Beamline `index.md` notes the lifecycle facets to be exercised per scenario.
