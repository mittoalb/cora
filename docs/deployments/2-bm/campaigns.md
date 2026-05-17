# Campaigns

*Campaign BC Campaigns registered at 2-BM. A Campaign composes Runs under a coordinated study (proposal-scoped, technique-tagged). See [Model](../../architecture/model.md) for the aggregate shape.*

| Campaign | `intent` | Tags | Status |
| --- | --- | --- | --- |
| `Proposal 2026-1234 beamtime` | `Coordinated` | `proposal`, `tomography`, `porous_media` | `Closed` (1 Run member; published in O-6) |
| `Proposal 2026-1234 continuous-rotation series` | `Series` | `proposal`, `continuous_rotation`, `tomography`, `porous_media` | `Planned` (3 Run members; close_campaign not exercised in this scenario) |
| `Proposal 2026-1236 2x2 tile mosaic` | `Coordinated` | `proposal`, `mosaic`, `tomography`, `porous_media` | `Planned` (4 tile Run members; close_campaign not exercised) |
| `Proposal 2026-1237 multi-energy contrast study` | `Coordinated` | `proposal`, `tomography`, `multi_energy`, `porous_media` | `Planned` (2 Run members spanning two distinct Plans; close_campaign not exercised) |

Source of truth: [`apps/api/tests/integration/scenarios/test_2bm_beamtime_intake.py`](../../../apps/api/tests/integration/scenarios/test_2bm_beamtime_intake.py) (genesis in `Planned`), [`apps/api/tests/integration/scenarios/test_2bm_tomography_scan.py`](../../../apps/api/tests/integration/scenarios/test_2bm_tomography_scan.py) (Run added via `add_run_to_campaign`), [`apps/api/tests/integration/scenarios/test_2bm_data_publish.py`](../../../apps/api/tests/integration/scenarios/test_2bm_data_publish.py) (`start_campaign` Planned -> Active, then `close_campaign` Active -> Closed), [`apps/api/tests/integration/scenarios/test_2bm_mosaic_acquisition.py`](../../../apps/api/tests/integration/scenarios/test_2bm_mosaic_acquisition.py) (Coordinated mosaic), [`apps/api/tests/integration/scenarios/test_2bm_energy_change.py`](../../../apps/api/tests/integration/scenarios/test_2bm_energy_change.py) (Coordinated multi-energy with operator pivot Decision).

The Campaign was opened by the operator during beamtime intake; `lead_actor_id` resolves to `Dr. PI (Proposal 2026-1234 lead)` (see [Argonne Actors](../argonne/actors.md)), `subject_id` resolves to the registered sandstone-core Subject (see [Subjects](subjects.md)). Lifecycle exercised end-to-end: `Planned` (intake) -> `Active` (start_campaign at publish time) -> `Closed` (close_campaign at publish time, locking membership).

## Pending in code

The following Campaigns are surfaced by the [2-BM repo survey](https://github.com/xray-imaging/2bm-docs) but not yet registered in code. Each materializes as a row above when its scenario test (or a seed script) registers it.

| Pending Campaign | `intent` | Tags | Source scenario (planned) |
| --- | --- | --- | --- |
| Alignment-chain orchestration | `Coordinated` | `alignment`, `auto_chain` | `tests/integration/scenarios/test_2bm_alignment_auto_chain.py` (composes the 5 alignment Runs + calibration + a Step-1 re-run; mirrors `align/auto.py` orchestration) |
| In-situ / operando study | `Coordinated` | `in_situ`, `operando` | Not yet sourced; would land when an operations-phase scenario exercises external-environment-driven Runs over time |
| Energy sweep | `Sweep` | `energy_sweep`, `xanes` | Not yet sourced; would land when a fine-grained per-energy-point sweep scenario lands (the existing `test_2bm_energy_change` is a 2-point `Coordinated` pivot, not an N-point `Sweep`) |
| Block-design experiment | `Block` | `block_design` | Not yet sourced; would land when a treatment-block-replicate experimental shape lands at 2-BM |

Per the [Campaign design](../../architecture/model.md), Campaigns:

- Have bidirectional composition with Runs (`Campaign.run_ids` <-> `Run.campaign_id`).
- Require `lead_actor_id` at creation.
- Carry LOOSE Subject coherence (a Campaign may span multiple Subjects).
- Have no Plan binding (the same Campaign may compose Runs from different Plans).
- Follow 5-state FSM `Planned -> Active -> Held -> Closed | Abandoned`.

Tomolog publication (per `ops/item_030.rst`) renders the Campaign + child Runs into Google Slides via the abstract `LogbookMirrorPort`; an implementor lands when the first operations-phase scenario integrates with the publication path.
