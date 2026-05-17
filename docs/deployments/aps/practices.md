# Practices

*Recipe BC Practices with `site_id` pointing to the APS Site Asset. A Practice is ISA-88's Site Recipe: the facility-adapted form of a Method. See [Model](../../architecture/model.md) for the aggregate shape.*

| Practice | Method | Purpose |
| --- | --- | --- |
| `APS_standard_flat_field_practice` | [`flat_field_correction`](../../catalog/methods.md) | APS's facility-standard binding of the flat-field correction technique |
| `APS_motor_homing_practice` | [`motor_homing`](../../catalog/methods.md) | APS's binding of the `motor_homing` Method for shakedown of any beamline's motorized Devices |
| `35BM_resolution_practice` | [`resolution_alignment`](../../catalog/methods.md) | APS's binding of `resolution_alignment` against 2-BM's Optique Peter focus motor + image chain |
| `35BM_focus_practice` | [`focus_alignment`](../../catalog/methods.md) | APS's binding of `focus_alignment` against 2-BM's Sample_top_Z + image chain |
| `35BM_alignment_practice` | [`center_alignment`](../../catalog/methods.md) | APS's binding of `center_alignment` against 2-BM's alignment Assets |
| `35BM_roll_practice` | [`roll_alignment`](../../catalog/methods.md) | APS's binding of `roll_alignment` against 2-BM's Aerotech rotary + Sample_top_Roll + image chain |
| `35BM_pitch_practice` | [`pitch_alignment`](../../catalog/methods.md) | APS's binding of `pitch_alignment` against 2-BM's Aerotech rotary + Sample_top_Pitch + image chain |
| `35BM_first_light_practice` | [`first_light`](../../catalog/methods.md) | APS's binding of `first_light` against 2-BM's Shutter_35BM + image chain |
| `35BM_dark_baseline_practice` | [`detector_dark_baseline`](../../catalog/methods.md) | APS's binding of `detector_dark_baseline` against 2-BM's Shutter_35BM + image chain |
| `35BM_flat_baseline_practice` | [`detector_flat_baseline`](../../catalog/methods.md) | APS's binding of `detector_flat_baseline` against 2-BM's Shutter_35BM + image chain |

Source of truth: [`test_aps_facility.py`](../../../apps/api/tests/integration/scenarios/test_aps_facility.py), [`test_2bm_motor_homing.py`](../../../apps/api/tests/integration/scenarios/test_2bm_motor_homing.py), [`test_2bm_first_light.py`](../../../apps/api/tests/integration/scenarios/test_2bm_first_light.py), [`test_2bm_dark_baseline.py`](../../../apps/api/tests/integration/scenarios/test_2bm_dark_baseline.py), [`test_2bm_flat_baseline.py`](../../../apps/api/tests/integration/scenarios/test_2bm_flat_baseline.py), [`test_2bm_alignment_resolution.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_resolution.py), [`test_2bm_alignment_focus.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_focus.py), [`test_2bm_alignment_center.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_center.py), [`test_2bm_alignment_roll.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_roll.py), [`test_2bm_alignment_pitch.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_pitch.py).

## Pending in code

Science-acquisition Practices (Mitutoyo 5× / 50 µm LuAG / 25 keV for phase-contrast fly-scan, and the Mitutoyo 1.1× and 10× variants the Optique Peter microscope supports) are not yet defined in code. Each lands as a row above when a scenario test or seed script defines it.
