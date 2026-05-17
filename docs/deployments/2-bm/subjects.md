# Subjects

*Subject BC Subjects registered at 2-BM. A Subject is the sample-or-thing being measured (proposal-anchored at operations phase, kinematic-mounted at acquisition time). See [Model](../../architecture/model.md) for the aggregate shape.*

| Subject | Class | Proposal | Status |
| --- | --- | --- | --- |
| `porous sandstone core (Proposal 2026-1234, sample A)` | porous-media core (sandstone) | `2026-1234` | `Received` |

Source of truth: [`apps/api/tests/integration/scenarios/test_2bm_beamtime_intake.py`](../../../apps/api/tests/integration/scenarios/test_2bm_beamtime_intake.py).

## Pending in code

The following Subjects are surfaced by the [2-BM repo survey](https://github.com/xray-imaging/2bm-docs) but not yet registered in code. Each materializes as a row above when its scenario test (or a seed script) registers it.

| Pending Subject | Class | Source scenario (planned) |
| --- | --- | --- |
| Mounted sandstone core (post-mount lifecycle transition) | Same Subject as above, advanced to `Mounted` | `tests/integration/scenarios/test_2bm_mount_sample.py` (Phase O-2: Subject lifecycle `Received -> Mounted`) |
| Proposal co-I sample roster | Multi-sample-class per proposal | `tests/integration/scenarios/test_2bm_beamtime_intake.py` (extension: `dmagic` pulls proposal metadata + tags TomoScan IOC; PI + co-Is registered as Actors, samples as Subjects) |
| Mosaic-acquisition shared Subject | Single Subject under Campaign(intent=Coordinated) | `tests/integration/scenarios/test_2bm_mosaic_acquisition.py` (N tiled scans share one Subject) |
| Continuous-rotation shared Subject | Single Subject under Campaign(intent=Series) | `tests/integration/scenarios/test_2bm_continuous_rotation_sweep.py` (N back-to-back acquisitions on one mounted sample) |
| Calibration phantom (Siemens star, USAF 1951, sphere) | Calibration-class Subject (kinematic-mounted, no proposal) | Not yet sourced as its own scenario; the alignment scenarios use sphere fixtures inline today without registering them as Subjects |

The Subject BC supports `Mounted -> Measured -> Received` lifecycle (per [Subject mount alignment design](../../architecture/model.md)); operations-phase scenarios will exercise the full cycle. Beamline `index.md` notes the lifecycle facets to be exercised per scenario.
