Operator-started Plan executions, from `start_run` through terminal state to Dataset registration. The most varied cluster: each acquisition mode CORA learns to express adds one or more scenarios here, and the lifecycle has multiple terminal shapes that each get their own canonical example.

- **Acquisition modes**: `tomography_scan` is the canonical happy path; `continuous_rotation_sweep` (Series Campaign, N=3 children), `mosaic_acquisition` (Coordinated Campaign, tile offsets), `streaming_tomography` (mid-flight `adjust_run` parameter steering), `data_publish` (Dataset promotion to `Production`), `energy_change` (cross-Plan operator-Decision pivot, the named-exception compendium), and `run_reading_logbook` (lazy-open RunReading append).
- **Lifecycle edge cases**: `run_hold_resume_cycle` (mid-flight Hold + Resume), `run_stopped_early` (controlled exit, partial data valid), `run_truncated_after_outage` (retroactive truncate after a control-room incident), `dismount_sample` (closes the Subject lifecycle `Mounted → Received`).

When this cluster crosses 15 scenarios, split acquisition modes from lifecycle edges into separate pages.
