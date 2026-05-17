# Datasets

*Data BC Datasets registered at 35-BM. A Dataset records an already-existing artifact (URI + checksum + byte_size + encoding) plus optional cross-aggregate refs (`producing_run_id`, `subject_id`, `derived_from`). See [Model](../../architecture/model.md) for the aggregate shape.*

| Dataset | Intent | Producing Run | Subject | Conforms to |
| --- | --- | --- | --- | --- |
| `35BM_dark_baseline_2026-04-17` | `Trial` | none (calibration) | none (no sample) | `https://www.nexusformat.org/NXdark_field` |
| `35BM_flat_baseline_2026-04-17` | `Trial` | none (calibration) | none (no sample) | `https://www.nexusformat.org/NXflat_field` |

Source of truth: [`test_35bm_commissioning_dark_baseline.py`](../../../apps/api/tests/integration/scenarios/test_35bm_commissioning_dark_baseline.py), [`test_35bm_commissioning_flat_baseline.py`](../../../apps/api/tests/integration/scenarios/test_35bm_commissioning_flat_baseline.py).

## Calibration Datasets (no Subject, no Run)

Dark and flat baselines are calibration artifacts that exist independent of any sample or science Run. They carry `subject_id=None` and `producing_run_id=None` per the [Data BC design](../../architecture/model.md): the design memo explicitly notes "subject_id: None for calibration / dark-field / synthetic data with no sample." Production-phase science Runs reference these baselines via the reconstruction formula:

```
reconstructed_projection = (raw - dark) / (flat - dark)
```

without the Run aggregate needing to know which specific baseline file it consumed; that linkage lives downstream in reconstruction-pipeline metadata.

## Intent and promotion

Both baselines land as `intent=Trial`. The `promote_dataset` slice (deferred at 35-BM) gates Production: a baseline only transitions to Production after operator review (signal-level + uniformity + hot-pixel count meet operational thresholds). For the commissioning-phase scenarios captured here, Trial is the expected resting state.

## Pending in code

Other Dataset types are not yet registered at 35-BM:

- **Raw projection stacks** produced by science Runs (require Subject + Run + operations-phase scenario; the entire `operations` phase is currently empty).
- **Reconstructed volumes** (derived from raw + dark + flat via `tomopy`; `derived_from` would carry all three Dataset ids).
- **Segmentation masks** (derived from reconstructions; further down the lineage chain).
- **Dark-subtracted flats** (the `derived_from` example mentioned in the flat-baseline scenario's gap-finding notes).

Each lands as a row above when a scenario test or seed script registers it.
