# Datasets

*Data BC Datasets registered at 2-BM. A Dataset records an already-existing artifact (URI + checksum + byte_size + encoding) plus optional cross-aggregate refs (`producing_run_id`, `subject_id`, `derived_from`). See [Model](../../architecture/model.md) for the aggregate shape.*

*See [Scenarios](../../scenarios/index.md) for the operator routines that exercise this surface.*

| Dataset | Intent · Format | Lineage (Run → Subject) | Scenario |
| --- | --- | --- | --- |
| `2BM_dark_baseline_2026-04-17` | `Trial` · `NXdark_field` | none → none | `dark_baseline` |
| `2BM_flat_baseline_2026-04-17` | `Trial` · `NXflat_field` | none → none | `flat_baseline` |
| `Proposal_2026-1234_sample_A_tomo` | `Trial → Production` · `NXtomo` (`promote_dataset`) | `Proposal 2026-1234 sample A tomography` → `porous sandstone core (Proposal 2026-1234, sample A)` | `tomography_scan` (genesis), `data_publish` (promotion) |
| `Proposal_2026-1234_sample_A_rotation_{01..03}` | `Trial` (N=3) · `NXtomo` | 3 rotation Runs under a Series Campaign → `porous sandstone core (Proposal 2026-1234, sample A, continuous rotation)` | `continuous_rotation_sweep` |
| `Proposal_2026-1236_mosaic_tile_{00..03}` | `Trial` (N=4) · `NXtomo` | 4 tile Runs under a Coordinated Campaign → `wide sandstone slab (Proposal 2026-1236, mosaic acquisition)` | `mosaic_acquisition` |
| `Proposal_2026-1237_low_energy_25keV` / `..._high_energy_30keV` | `Trial` (N=2) · `NXtomo` | 2 Runs on distinct low/high-energy Plans → `iron-bearing sandstone core (Proposal 2026-1237, energy-pivot study)` | `energy_change` |
| `Proposal_2026-1234_sample_A_streaming_snapshot` | `Trial` · `NXtomo` | streaming tomography Run with mid-flight `adjust_run` → `porous sandstone core (Proposal 2026-1234, sample A)` | `streaming_tomography` |
| `Sample_of_opportunity_partial_600proj` | `Trial` · `NXtomo` | `Stopped` Run (1500 projections planned, 600 actually captured) → `leftover sandstone core (sample-of-opportunity)` | `run_stopped_early` |

## Calibration Datasets (no Subject, no Run)

Dark and flat baselines carry `subject_id=None` and `producing_run_id=None`. Downstream science Runs consume them via the reconstruction formula `(raw - dark) / (flat - dark)`; that linkage lives in reconstruction-pipeline metadata, not on the Run aggregate.

## Pending

Dataset classes planned for 2-BM but not yet present in the inventory above.

- **Rocking curve** (`Trial`) — channel-cut-crystal scan output.
- **Vibration baseline** (`Trial`) — 1000-frame stack.
- **Globus / FDT push to Petrel** — external transport, not a Dataset event in itself; complements `data_publish` once a `LogbookMirrorPort` implementor exists.
- **Reconstructed volume** (`Production`) — `derived_from` would carry raw + dark + flat.
- **Segmentation mask** (`Production`) — further down the lineage chain.
- **Dark-subtracted flat** (`Trial`) — `derived_from` would point at both baselines.
