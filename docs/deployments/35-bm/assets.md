# Assets

*Equipment BC Assets registered at 35-BM. See [Model](../../architecture/model.md) for the aggregate shape.*

| Asset | Capability | Role at 35-BM |
| --- | --- | --- |
| `Aerotech_ABRS_rotary` | `RotaryStage` | Rotation axis; the motor driven 0° → 180° during alignment iterations and during fly-scan acquisition |
| `Sample_top_X` | `LinearStage` | X-correction motor (Kohzu CYAT-070); the linear stage nudged to close rotation-axis offset |
| `Sample_top_Z` | `LinearStage` | Sample-to-scintillator distance motor (cm range, ~10µm resolution); tunes depth-of-focus and projection magnification together |
| `Sample_top_Roll` | `LinearStage` | Roll-tilt motor under the rotation stage; small-angle (milliradian) corrections to keep the rotation axis perpendicular to the camera Y axis |
| `Sample_top_Pitch` | `LinearStage` | Pitch-tilt motor under the rotation stage; orthogonal to Sample_top_Roll; corrects out-of-plane axis tilt (toward/away from camera) |
| `Optique_Peter_focus_Z` | `LinearStage` | Focus motor inside the Optique Peter microscope; sub-micron resolution lens-to-scintillator distance |
| `Shutter_35BM` | `Shutter` | Safety shutter at the 35-BM front-end; opens to admit beam, closes for safe state |
| `Oryx_5MP_camera` | `Camera` | Alignment-frame detector (FLIR ORX-10G-51S5M-C, 2448 × 2048, 3.45 µm) |
| `Scintillator_LuAG` | `Scintillator` | LuAG scintillator; converts X-rays to visible light for the camera |

Source of truth: [`test_35bm_beta_alignment_center_scenario.py`](../../../apps/api/tests/integration/test_35bm_beta_alignment_center_scenario.py), [`test_35bm_shakedown_motor_homing_scenario.py`](../../../apps/api/tests/integration/test_35bm_shakedown_motor_homing_scenario.py), [`test_35bm_commissioning_first_light_scenario.py`](../../../apps/api/tests/integration/test_35bm_commissioning_first_light_scenario.py), [`test_35bm_beta_alignment_resolution_scenario.py`](../../../apps/api/tests/integration/test_35bm_beta_alignment_resolution_scenario.py), [`test_35bm_beta_alignment_focus_scenario.py`](../../../apps/api/tests/integration/test_35bm_beta_alignment_focus_scenario.py), [`test_35bm_beta_alignment_roll_scenario.py`](../../../apps/api/tests/integration/test_35bm_beta_alignment_roll_scenario.py), [`test_35bm_beta_alignment_pitch_scenario.py`](../../../apps/api/tests/integration/test_35bm_beta_alignment_pitch_scenario.py).

## Lifecycle and condition coverage

Asset facets exercised in code today:

| Facet | Aerotech | Sample_top_X | Sample_top_Z | Sample_top_Roll | Sample_top_Pitch | Optique_Peter_focus_Z | Shutter_35BM | Oryx_5MP_camera | Scintillator_LuAG |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Lifecycle: `Commissioned → Active` | yes | yes | yes (focus) | yes (roll) | yes (pitch) | yes (resolution) | yes (first_light) | yes (resolution, focus, roll, pitch, first_light) | yes (resolution, focus, roll, pitch, first_light) |
| Condition: `Nominal → Degraded → Nominal` | yes (cold-start home failure → retry) | no | no | no | no | no | no | no | no |
| Caution attached | yes ([Aerotech cold-start index miss](cautions.md)) | no | no | no | no | no | no | no | no |

Lifecycle transitions on Oryx and Scintillator land in every alignment + first-light scenario that consumes the image chain; their condition / Caution facets remain unexercised until further commissioning scenarios surface operator pain points.

## Settings (Phase 10e-a)

`Capability.settings_schema` declares the *intrinsic property contract* for a device class (positions, encoder resolution, hardware envelope, per-install calibration). `Asset.settings` carries this specific device's values. Runtime parameters (exposure, energy, rotation step) live on `Method.parameters_schema` instead and land in 10e-b.

Every numeric property carries a `unit: {system, code}` annotation per the [units design](../../architecture/model.md). The same-unit-per-physical-dimension-per-Capability convention means all RotaryStage angles are in `deg`, all LinearStage lengths in `mm`, etc. Different physical dimensions in the same Capability use different unit codes (positions in `deg` plus `max_speed` in `deg/s`).

| Asset (vendor) | Property | Value | Unit |
| --- | --- | --- | --- |
| `Aerotech_ABRS_rotary` (Aerotech ABRS) | `min_position` | -360 | `deg` |
| | `max_position` | 360 | `deg` |
| | `max_speed` | 720 | `deg/s` |
| | `encoder_resolution` | 0.0001 | `deg` |
| | `homing_offset` | 0 | `deg` |
| `Sample_top_X` (Kohzu CYAT-070) | `min_position` | -10 | `mm` |
| | `max_position` | 10 | `mm` |
| | `max_speed` | 1 | `mm/s` |
| | `encoder_resolution` | 0.0005 | `mm` |
| `Oryx_5MP_camera` (FLIR ORX-10G-51S5M-C) | `sensor_width` | 2448 | `pixel` |
| | `sensor_height` | 2048 | `pixel` |
| | `pixel_size` | 3.45 | `um` |
| | `bit_depth` | 12 | `bit` |
| `Scintillator_LuAG` (LuAG:Ce) | `thickness` | 100 | `um` |
| | `decay_time` | 0.07 | `us` |

Source of truth: [`test_35bm_beta_alignment_center_scenario.py`](../../../apps/api/tests/integration/test_35bm_beta_alignment_center_scenario.py) (the `_SCHEMA_*` + `_SETTINGS_*` constants near the top of the file) plus the unit-tier coverage at [`tests/unit/equipment/test_pilot_capability_schemas.py`](../../../apps/api/tests/unit/equipment/test_pilot_capability_schemas.py).

## Pending in code

The broader 35-BM Asset stack (softGlueZynq FPGA, the full Optique Peter triple-objective microscope with three lens / scintillator options, the PCO Dimax HS high-speed detector, sample-stage X/Y/Z/pitch/roll motors, the hexapod) is not yet registered in code. Each lands as a row above when a scenario test or seed script instantiates it.
