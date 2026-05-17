# Capabilities

*Equipment BC Capabilities. A Capability names a kind of thing an Asset can do, and is the contract by which a Method declares the device types its realizations need. Capabilities are cross-facility vocabulary, not bound to any Site. See [Model](../architecture/model.md) for the aggregate shape.*

| Capability | Used by Methods |
| --- | --- |
| `RotaryStage` | `motor_homing`, `center_alignment`, `roll_alignment`, `pitch_alignment` |
| `LinearStage` | `motor_homing`, `resolution_alignment`, `focus_alignment`, `center_alignment`, `roll_alignment`, `pitch_alignment` |
| `Camera` | `resolution_alignment`, `focus_alignment`, `center_alignment`, `roll_alignment`, `pitch_alignment`, `first_light` |
| `Scintillator` | `resolution_alignment`, `focus_alignment`, `center_alignment`, `roll_alignment`, `pitch_alignment`, `first_light` |
| `Shutter` | `first_light` |
| `ProbeGeneric` | `flat_field_correction` |

Source of truth: [`test_aps_install_facility.py`](../../apps/api/tests/integration/scenarios/test_aps_install_facility.py), [`test_35bm_shakedown_motor_homing.py`](../../apps/api/tests/integration/scenarios/test_35bm_shakedown_motor_homing.py), [`test_35bm_commissioning_first_light.py`](../../apps/api/tests/integration/scenarios/test_35bm_commissioning_first_light.py), [`test_35bm_commissioning_dark_baseline.py`](../../apps/api/tests/integration/scenarios/test_35bm_commissioning_dark_baseline.py), [`test_35bm_commissioning_flat_baseline.py`](../../apps/api/tests/integration/scenarios/test_35bm_commissioning_flat_baseline.py), [`test_35bm_beta_alignment_resolution.py`](../../apps/api/tests/integration/scenarios/test_35bm_beta_alignment_resolution.py), [`test_35bm_beta_alignment_focus.py`](../../apps/api/tests/integration/scenarios/test_35bm_beta_alignment_focus.py), [`test_35bm_beta_alignment_center.py`](../../apps/api/tests/integration/scenarios/test_35bm_beta_alignment_center.py), [`test_35bm_beta_alignment_roll.py`](../../apps/api/tests/integration/scenarios/test_35bm_beta_alignment_roll.py), [`test_35bm_beta_alignment_pitch.py`](../../apps/api/tests/integration/scenarios/test_35bm_beta_alignment_pitch.py).

## Pending in code

Beamline-typical Capabilities (`HighSpeedCamera`, `Hexapod`, `Goniometer`, `Monochromator`, `Slit`) are not yet defined. Each lands as a row above when a scenario test or seed script defines it.
