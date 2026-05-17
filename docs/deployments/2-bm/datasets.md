# Datasets

*Data BC Datasets registered at 2-BM. A Dataset records an already-existing artifact (URI + checksum + byte_size + encoding) plus optional cross-aggregate refs (`producing_run_id`, `subject_id`, `derived_from`). See [Model](../../architecture/model.md) for the aggregate shape.*

| Dataset | Intent | Producing Run | Subject | Conforms to |
| --- | --- | --- | --- | --- |
| `2BM_dark_baseline_2026-04-17` | `Trial` | none (calibration) | none (no sample) | `https://www.nexusformat.org/NXdark_field` |
| `2BM_flat_baseline_2026-04-17` | `Trial` | none (calibration) | none (no sample) | `https://www.nexusformat.org/NXflat_field` |
| `Proposal_2026-1234_sample_A_tomo` | `Production` (promoted from `Trial` after operator review) | `Proposal 2026-1234 sample A tomography` Run | `porous sandstone core (Proposal 2026-1234, sample A)` | `https://www.nexusformat.org/NXtomo` |
| `Proposal_2026-1234_sample_A_rotation_{01..03}` | `Trial` (N=3) | three back-to-back rotation Runs under a Series Campaign | `porous sandstone core (Proposal 2026-1234, sample A, continuous rotation)` | `https://www.nexusformat.org/NXtomo` |
| `Proposal_2026-1236_mosaic_tile_{00..03}` | `Trial` (N=4 tiles) | four tile Runs under a Coordinated Campaign | `wide sandstone slab (Proposal 2026-1236, mosaic acquisition)` | `https://www.nexusformat.org/NXtomo` |
| `Proposal_2026-1237_low_energy_25keV` / `..._high_energy_30keV` | `Trial` (N=2) | two Runs on distinct low/high-energy Plans under a Coordinated Campaign | `iron-bearing sandstone core (Proposal 2026-1237, energy-pivot study)` | `https://www.nexusformat.org/NXtomo` |

Source of truth: [`test_2bm_dark_baseline.py`](../../../apps/api/tests/integration/scenarios/test_2bm_dark_baseline.py), [`test_2bm_flat_baseline.py`](../../../apps/api/tests/integration/scenarios/test_2bm_flat_baseline.py), [`test_2bm_tomography_scan.py`](../../../apps/api/tests/integration/scenarios/test_2bm_tomography_scan.py) (Trial genesis), [`test_2bm_data_publish.py`](../../../apps/api/tests/integration/scenarios/test_2bm_data_publish.py) (Trial -> Production promotion), [`test_2bm_continuous_rotation_sweep.py`](../../../apps/api/tests/integration/scenarios/test_2bm_continuous_rotation_sweep.py) (N=3 rotation Trials), [`test_2bm_mosaic_acquisition.py`](../../../apps/api/tests/integration/scenarios/test_2bm_mosaic_acquisition.py) (N=4 tile Trials), [`test_2bm_energy_change.py`](../../../apps/api/tests/integration/scenarios/test_2bm_energy_change.py) (low/high-energy Trials).

## Calibration Datasets (no Subject, no Run)

Dark and flat baselines are calibration artifacts that exist independent of any sample or science Run. They carry `subject_id=None` and `producing_run_id=None` per the [Data BC design](../../architecture/model.md): the design memo explicitly notes "subject_id: None for calibration / dark-field / synthetic data with no sample." Production-phase science Runs reference these baselines via the reconstruction formula:

```
reconstructed_projection = (raw - dark) / (flat - dark)
```

without the Run aggregate needing to know which specific baseline file it consumed; that linkage lives downstream in reconstruction-pipeline metadata.

## Intent and promotion

Both baselines land as `intent=Trial`. The `promote_dataset` slice (deferred at 2-BM) gates Production: a baseline only transitions to Production after operator review (signal-level + uniformity + hot-pixel count meet operational thresholds). For the commissioning-phase scenarios captured here, Trial is the expected resting state.

## Pending in code

Other Dataset types surfaced by the [2-BM repo survey](https://github.com/xray-imaging/2bm-docs) or design notes. Each lands as a row above when a scenario test (or seed script) registers it.

| Pending Dataset class | Intent at registration | Source scenario (planned) |
| --- | --- | --- |
| Live-reconstruction projection (streaming) | `Trial` | `tests/integration/scenarios/test_2bm_streaming_tomography.py` (TomoScanStream + tomoStream) |
| Rocking curve | `Trial` | `tests/integration/scenarios/test_2bm_energy_calibration.py` (channel-cut-crystal scan to measure true DMM energy) |
| Vibration baseline (1000-frame stack) | `Trial` | `tests/integration/scenarios/test_2bm_vibration_baseline.py` (pre / post air-handler shutdown comparison) |
| Globus / FDT push to Petrel | (external transport, not a Dataset event) | Not yet sourced; LogbookMirrorPort implementor would complement `test_2bm_data_publish.py` once Olog/SciLog/SciCat integration lands |
| Reconstructed volume | `Production` | Not yet sourced; downstream of raw + dark + flat via `tomopy`; `derived_from` would carry all three Dataset ids |
| Segmentation mask | `Production` | Not yet sourced; further down the lineage chain |
| Dark-subtracted flat | `Trial` | Not yet sourced; `derived_from` would point at both dark + flat baselines |
