# Families

*Equipment BC Families. A Family names a kind of thing an Asset can do (device-class abstraction), and is the contract by which a Method declares the device types its realizations need (via `needed_family_ids`). Each Family carries a set of [Affordances](../reference/affordances.md) — the primitive operations the device-class supports — which the cross-BC Plan-binding matching engine compares against the Method's bound [Capability](capabilities.md)'s `required_affordances`. Families are cross-facility vocabulary, not bound to any Site. See [Model](../architecture/model.md) for the aggregate shape.*

| Family | Used by Methods |
| --- | --- |
| `RotaryStage` | `motor_homing`, `center_alignment`, `roll_alignment`, `pitch_alignment`, `alignment_calibration`, `tomography`, `streaming_tomography`, `continuous_rotation_tomography`, `mosaic_tomography` |
| `LinearStage` | `motor_homing`, `resolution_alignment`, `focus_alignment`, `center_alignment`, `roll_alignment`, `pitch_alignment`, `alignment_calibration`, `tomography`, `streaming_tomography`, `continuous_rotation_tomography`, `mosaic_tomography` |
| `Camera` | `resolution_alignment`, `focus_alignment`, `center_alignment`, `roll_alignment`, `pitch_alignment`, `first_light`, `dark_baseline`, `flat_baseline`, `alignment_calibration`, `tomography`, `streaming_tomography`, `continuous_rotation_tomography`, `mosaic_tomography` |
| `Scintillator` | `resolution_alignment`, `focus_alignment`, `center_alignment`, `roll_alignment`, `pitch_alignment`, `first_light`, `dark_baseline`, `flat_baseline`, `alignment_calibration`, `tomography`, `streaming_tomography`, `continuous_rotation_tomography`, `mosaic_tomography` |
| `Shutter` | `first_light`, `dark_baseline`, `flat_baseline` |
| `ProbeGeneric` | `dark_baseline` (APS facility-scope template — abstract detector probe-chain) |
| `Hexapod` | `hexapod_reboot` |
| `Microscope` | `mctoptics_image_acquisition` (2-BM Optique Peter detector parent Assembly) |
| `Objective` | `mctoptics_image_acquisition` (per-lens identity inside a `Microscope` turret) |

Source of truth: [`test_aps_facility.py`](../../apps/api/tests/integration/scenarios/test_aps_facility.py), [`test_2bm_motor_homing.py`](../../apps/api/tests/integration/scenarios/test_2bm_motor_homing.py), [`test_2bm_first_light.py`](../../apps/api/tests/integration/scenarios/test_2bm_first_light.py), [`test_2bm_dark_baseline.py`](../../apps/api/tests/integration/scenarios/test_2bm_dark_baseline.py), [`test_2bm_flat_baseline.py`](../../apps/api/tests/integration/scenarios/test_2bm_flat_baseline.py), [`test_2bm_alignment_resolution.py`](../../apps/api/tests/integration/scenarios/test_2bm_alignment_resolution.py), [`test_2bm_alignment_focus.py`](../../apps/api/tests/integration/scenarios/test_2bm_alignment_focus.py), [`test_2bm_alignment_center.py`](../../apps/api/tests/integration/scenarios/test_2bm_alignment_center.py), [`test_2bm_alignment_roll.py`](../../apps/api/tests/integration/scenarios/test_2bm_alignment_roll.py), [`test_2bm_alignment_pitch.py`](../../apps/api/tests/integration/scenarios/test_2bm_alignment_pitch.py), [`test_2bm_hexapod_reboot.py`](../../apps/api/tests/integration/scenarios/test_2bm_hexapod_reboot.py), [`test_2bm_mctoptics_setup.py`](../../apps/api/tests/integration/scenarios/test_2bm_mctoptics_setup.py).

## Pending in code

Beamline-typical Families (`HighSpeedCamera`, `Goniometer`, `Monochromator`, `Slit`, `Mirror`, `TriggerFPGA`) are not yet defined. Each lands as a row above when a scenario test or seed script defines it.
