# Methods

*Recipe BC Methods. A Method names a technique abstractly (ISA-88 General Recipe layer) and declares the Capabilities its realizations must offer. Methods are cross-facility vocabulary, not bound to any Site. See [Model](../architecture/model.md) for the aggregate shape.*

| Method | Needed capabilities | Purpose |
| --- | --- | --- |
| `motor_homing` | `RotaryStage`, `LinearStage` | Reference-position seek for one or more motorized Devices; produces motors with encoders zeroed and ready for absolute-coordinate moves |
| `resolution_alignment` | `LinearStage`, `Camera`, `Scintillator` | The `resolution` step in the rotation-axis alignment chain; iterative focus-Z peak search on a mounted resolution target |
| `focus_alignment` | `LinearStage`, `Camera`, `Scintillator` | The `focus` step in the rotation-axis alignment chain; iterative Sample-Z peak search for depth-of-focus on the mounted sample |
| `center_alignment` | `RotaryStage`, `LinearStage`, `Camera`, `Scintillator` | The `center` step in the rotation-axis alignment chain; iterative 0°/180° convergence on the calibrated rotation-axis pixel position |
| `roll_alignment` | `RotaryStage`, `LinearStage`, `Camera`, `Scintillator` | The `roll` step in the rotation-axis alignment chain; iterative 0°/180° Y-delta correction to make the rotation axis perpendicular to the camera Y axis |
| `pitch_alignment` | `RotaryStage`, `LinearStage`, `Camera`, `Scintillator` | The `pitch` step in the rotation-axis alignment chain; iterative 0°/180° sharpness-delta correction to make the rotation axis perpendicular to the beam direction |
| `first_light` | `Shutter`, `Camera`, `Scintillator` | The canonical commissioning milestone; dark + first-light + safe-state frame ceremony confirming beam reaches the detector |
| `detector_dark_baseline` | `Shutter`, `Camera`, `Scintillator` | Dark-frame stack acquisition + pixel-wise baseline computation, producing a Dataset for reconstruction subtraction |
| `detector_flat_baseline` | `Shutter`, `Camera`, `Scintillator` | Flat-field stack acquisition (shutter open, no sample) + pixel-wise baseline computation, producing a Dataset for reconstruction division |
| `flat_field_correction` | `ProbeGeneric` | Flat-field (white-field / dark-field) correction baseline applied prior to reconstruction |

Source of truth: [`test_aps_facility.py`](../../apps/api/tests/integration/scenarios/test_aps_facility.py), [`test_2bm_motor_homing.py`](../../apps/api/tests/integration/scenarios/test_2bm_motor_homing.py), [`test_2bm_first_light.py`](../../apps/api/tests/integration/scenarios/test_2bm_first_light.py), [`test_2bm_dark_baseline.py`](../../apps/api/tests/integration/scenarios/test_2bm_dark_baseline.py), [`test_2bm_flat_baseline.py`](../../apps/api/tests/integration/scenarios/test_2bm_flat_baseline.py), [`test_2bm_alignment_resolution.py`](../../apps/api/tests/integration/scenarios/test_2bm_alignment_resolution.py), [`test_2bm_alignment_focus.py`](../../apps/api/tests/integration/scenarios/test_2bm_alignment_focus.py), [`test_2bm_alignment_center.py`](../../apps/api/tests/integration/scenarios/test_2bm_alignment_center.py), [`test_2bm_alignment_roll.py`](../../apps/api/tests/integration/scenarios/test_2bm_alignment_roll.py), [`test_2bm_alignment_pitch.py`](../../apps/api/tests/integration/scenarios/test_2bm_alignment_pitch.py).

## Pending in code

Science-acquisition Methods (phase-contrast micro-CT fly-scan, nano-CT with FZP, MHz imaging, energy scan, XAS) are not yet defined. Each lands as a row above when a scenario test or seed script registers it.
