# Capabilities

*Equipment BC Families. A Family names a kind of thing an Asset can do, and is the contract by which a Method declares the device types its realizations need. Families are cross-facility vocabulary, not bound to any Site. See [Model](../architecture/model.md) for the aggregate shape.*

| Family | Used by Methods |
| --- | --- |
| `RotaryStage` | `motor_homing`, `center_alignment`, `roll_alignment`, `pitch_alignment` |
| `LinearStage` | `motor_homing`, `resolution_alignment`, `focus_alignment`, `center_alignment`, `roll_alignment`, `pitch_alignment` |
| `Camera` | `resolution_alignment`, `focus_alignment`, `center_alignment`, `roll_alignment`, `pitch_alignment`, `first_light` |
| `Scintillator` | `resolution_alignment`, `focus_alignment`, `center_alignment`, `roll_alignment`, `pitch_alignment`, `first_light` |
| `Shutter` | `first_light` |
| `ProbeGeneric` | `flat_field_correction` |
| `Hexapod` | `hexapod_reboot` |

Source of truth: [`test_aps_facility.py`](../../apps/api/tests/integration/scenarios/test_aps_facility.py), [`test_2bm_motor_homing.py`](../../apps/api/tests/integration/scenarios/test_2bm_motor_homing.py), [`test_2bm_first_light.py`](../../apps/api/tests/integration/scenarios/test_2bm_first_light.py), [`test_2bm_dark_baseline.py`](../../apps/api/tests/integration/scenarios/test_2bm_dark_baseline.py), [`test_2bm_flat_baseline.py`](../../apps/api/tests/integration/scenarios/test_2bm_flat_baseline.py), [`test_2bm_alignment_resolution.py`](../../apps/api/tests/integration/scenarios/test_2bm_alignment_resolution.py), [`test_2bm_alignment_focus.py`](../../apps/api/tests/integration/scenarios/test_2bm_alignment_focus.py), [`test_2bm_alignment_center.py`](../../apps/api/tests/integration/scenarios/test_2bm_alignment_center.py), [`test_2bm_alignment_roll.py`](../../apps/api/tests/integration/scenarios/test_2bm_alignment_roll.py), [`test_2bm_alignment_pitch.py`](../../apps/api/tests/integration/scenarios/test_2bm_alignment_pitch.py), [`test_2bm_hexapod_reboot.py`](../../apps/api/tests/integration/scenarios/test_2bm_hexapod_reboot.py).

## Pending in code

Beamline-typical Capabilities (`HighSpeedCamera`, `Goniometer`, `Monochromator`, `Slit`, `Mirror`, `TriggerFPGA`) are not yet defined. Each lands as a row above when a scenario test or seed script defines it.
