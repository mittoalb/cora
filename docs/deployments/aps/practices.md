# Practices

*Recipe BC Practices with `site_id` pointing to the APS Site Asset. A Practice is ISA-88's Site Recipe: the facility-adapted form of a Method. See [Model](../../architecture/model.md) for the aggregate shape.*

*See [Scenarios](../../scenarios/index.md) for the operator routines that exercise this surface.*

| Practice | Method | Beamline targets | Consuming scenario(s) |
| --- | --- | --- | --- |
| `APS_standard_flat_field_practice` | [`flat_field_correction`](../../catalog/methods.md) | facility-wide (Method binding) | (no scenario consumer yet) |
| `APS_motor_homing_practice` | [`motor_homing`](../../catalog/methods.md) | 2-BM motorized Devices | `motor_homing` |
| `2BM_resolution_practice` | [`resolution_alignment`](../../catalog/methods.md) | Optique_Peter_focus_Z + image chain | `alignment_resolution` |
| `2BM_focus_practice` | [`focus_alignment`](../../catalog/methods.md) | Sample_top_Z + image chain | `alignment_focus` |
| `2BM_alignment_practice` | [`center_alignment`](../../catalog/methods.md) | alignment Assets | `alignment_center` |
| `2BM_roll_practice` | [`roll_alignment`](../../catalog/methods.md) | Aerotech rotary + Sample_top_Roll + image chain | `alignment_roll` |
| `2BM_pitch_practice` | [`pitch_alignment`](../../catalog/methods.md) | Aerotech rotary + Sample_top_Pitch + image chain | `alignment_pitch` |
| `2BM_first_light_practice` | [`first_light`](../../catalog/methods.md) | Shutter_2BM + image chain | `first_light` |
| `2BM_dark_baseline_practice` | [`detector_dark_baseline`](../../catalog/methods.md) | Shutter_2BM + image chain | `dark_baseline` |
| `2BM_flat_baseline_practice` | [`detector_flat_baseline`](../../catalog/methods.md) | Shutter_2BM + image chain | `flat_baseline` |
| `2BM_alignment_calibration_practice` | [`alignment_calibration`](../../catalog/methods.md) | roll + pitch motors (measures K_roll / K_pitch) | `alignment_calibration` |
| `2BM_hexapod_reboot_practice` | [`hexapod_reboot`](../../catalog/methods.md) | Hexapod_2BM | `hexapod_reboot` |
| `2BM_tomography_practice` | [`tomography_scan`](../../catalog/methods.md) | full sample + image chain | `tomography_scan`, `data_publish`, `run_debrief`, `run_debrief_degraded`, `run_debrief_aborted`, `run_reading_logbook`, `run_hold_resume_cycle`, `run_truncated_after_outage`, `run_stopped_early` |
| `2BM_streaming_tomography_practice` | [`streaming_tomography`](../../catalog/methods.md) | TomoScanStream + tomoStream Run (`adjust_run`) | `streaming_tomography` |
| `2BM_mosaic_practice` | [`tomography_scan`](../../catalog/methods.md) | sample-stage X / Y + image chain (N sibling Runs) | `mosaic_acquisition` |
| `2BM_continuous_rotation_practice` | [`continuous_rotation_tomography`](../../catalog/methods.md) | flyscan stage + image chain (N back-to-back Runs) | `continuous_rotation_sweep` |
| `2BM_multi_energy_practice` | [`tomography_scan`](../../catalog/methods.md) | low-keV + high-keV Plans under one Campaign | `energy_change` |

Source of truth: [`test_aps_facility.py`](../../../apps/api/tests/integration/scenarios/test_aps_facility.py) declares each Practice; consuming scenarios at [`test_2bm_<scenario>.py`](../../../apps/api/tests/integration/scenarios/) (one-to-one with the Consuming scenario column).

## Pending in code

Additional objective-specific Practices (Mitutoyo 1.1× / 5× / 10× variants the Optique Peter microscope supports; per-objective sample-Z + scintillator pairings) and maintenance Practices (`energy_calibration`, `ioc_restart`, `vibration_baseline`, `mirror_recoat_return`) are not yet defined in code. Each lands as a row above when a scenario test or seed script defines it.
