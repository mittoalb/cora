# Campaigns

*Campaign BC Campaigns registered at 2-BM. A Campaign composes Runs under a coordinated study (proposal-scoped, technique-tagged). See [Model](../../architecture/model.md) for the aggregate shape.*

| Campaign | `intent` | Tags | Status |
| --- | --- | --- | --- |

No 2-BM Campaigns are registered in code yet. The Campaign BC enters scope at operations phase: every proposal-driven beamtime yields at least one Campaign (the proposal itself), and intra-beamtime acquisition modes (continuous-rotation, mosaic, energy-sweep, in-situ) add further Campaigns with specific `intent` values.

## Pending in code

The following Campaigns are surfaced by the [2-BM repo survey](https://github.com/xray-imaging/2bm-docs) but not yet registered in code. Each materializes as a row above when its scenario test (or a seed script) registers it.

| Pending Campaign | `intent` | Tags | Source scenario (planned) |
| --- | --- | --- | --- |
| Proposal beamtime Campaign | `Coordinated` | `proposal`, `<technique-per-proposal>` | `tests/integration/scenarios/test_2bm_beamtime_intake.py` (proposal-scoped Campaign; lead_actor_id = PI; opens at beamtime start via `dmagic show` + `dmagic tag`) |
| Continuous-rotation sweep | `Series` | `tomography`, `continuous_rotation` | `tests/integration/scenarios/test_2bm_continuous_rotation_sweep.py` (N child Runs sharing one Plan; one TomoScan call collects 100 datasets x 1500 projections in one fly per `pre_apsu/ops/item_025.rst`) |
| Mosaic acquisition | `Coordinated` | `tomography`, `mosaic` | `tests/integration/scenarios/test_2bm_mosaic_acquisition.py` (parameter sweep across tile XY; filename pattern `<Subject>_mosaic_NNN.h5` per `ops/item_030.rst`) |
| Alignment-chain orchestration | `Coordinated` | `alignment`, `auto_chain` | `tests/integration/scenarios/test_2bm_alignment_auto_chain.py` (composes the 5 alignment Runs + calibration + a Step-1 re-run; mirrors `align/auto.py` orchestration) |
| In-situ / operando study | `Coordinated` | `in_situ`, `operando` | Not yet sourced; would land when an operations-phase scenario exercises external-environment-driven Runs over time |
| Energy sweep | `Sweep` | `energy_sweep`, `xanes` | Not yet sourced; would land when energy-scan operations scenarios exist |

Per the [Campaign design](../../architecture/model.md), Campaigns:

- Have bidirectional composition with Runs (`Campaign.run_ids` <-> `Run.campaign_id`).
- Require `lead_actor_id` at creation.
- Carry LOOSE Subject coherence (a Campaign may span multiple Subjects).
- Have no Plan binding (the same Campaign may compose Runs from different Plans).
- Follow 5-state FSM `Planned -> Active -> Held -> Closed | Abandoned`.

Tomolog publication (per `ops/item_030.rst`) renders the Campaign + child Runs into Google Slides via the abstract `LogbookMirrorPort`; an implementor lands when the first operations-phase scenario integrates with the publication path.
