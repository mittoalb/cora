# Assets

*Equipment BC Assets registered **under** the 2-BM Unit (the Devices that hang off it). The 2-BM Asset itself sits at the Unit level and is declared on the [2-BM index](index.md). See [Model](../../architecture/model.md) for the aggregate shape.*

| Asset | Capability | Role at 2-BM |
| --- | --- | --- |
| `Aerotech_ABRS_rotary` | `RotaryStage` | Rotation axis; the motor driven 0° → 180° during alignment iterations and during fly-scan acquisition |
| `Sample_top_X` | `LinearStage` | X-correction motor (Kohzu CYAT-070); the linear stage nudged to close rotation-axis offset |
| `Sample_top_Z` | `LinearStage` | Sample-to-scintillator distance motor (cm range, ~10µm resolution); tunes depth-of-focus and projection magnification together |
| `Sample_top_Roll` | `LinearStage` | Roll-tilt motor under the rotation stage; small-angle (milliradian) corrections to keep the rotation axis perpendicular to the camera Y axis |
| `Sample_top_Pitch` | `LinearStage` | Pitch-tilt motor under the rotation stage; orthogonal to Sample_top_Roll; corrects out-of-plane axis tilt (toward/away from camera) |
| `Optique_Peter_focus_Z` | `LinearStage` | Focus motor inside the Optique Peter microscope; sub-micron resolution lens-to-scintillator distance |
| `Shutter_2BM` | `Shutter` | Safety shutter at the 2-BM front-end; opens to admit beam, closes for safe state |
| `Oryx_5MP_camera` | `Camera` | Alignment-frame detector (FLIR ORX-10G-51S5M-C, 2448 × 2048, 3.45 µm) |
| `Scintillator_LuAG` | `Scintillator` | LuAG scintillator; converts X-rays to visible light for the camera |
| `Hexapod_2BM` | `Hexapod` | PI sample-positioning hexapod (6-DOF); recoverable via `hexapod_reboot` Procedure when controller locks up |

Source of truth: [`test_2bm_alignment_center.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_center.py), [`test_2bm_motor_homing.py`](../../../apps/api/tests/integration/scenarios/test_2bm_motor_homing.py), [`test_2bm_first_light.py`](../../../apps/api/tests/integration/scenarios/test_2bm_first_light.py), [`test_2bm_dark_baseline.py`](../../../apps/api/tests/integration/scenarios/test_2bm_dark_baseline.py), [`test_2bm_flat_baseline.py`](../../../apps/api/tests/integration/scenarios/test_2bm_flat_baseline.py), [`test_2bm_alignment_resolution.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_resolution.py), [`test_2bm_alignment_focus.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_focus.py), [`test_2bm_alignment_roll.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_roll.py), [`test_2bm_alignment_pitch.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_pitch.py), [`test_2bm_hexapod_reboot.py`](../../../apps/api/tests/integration/scenarios/test_2bm_hexapod_reboot.py).

## Lifecycle and condition coverage

Asset facets exercised in code today (row-per-Asset; scales linearly as new Devices land in the inventory above):

| Asset | Activated (Commissioned → Active) | Condition cycle (Nominal → Degraded → Nominal) | Condition fault (Nominal → Faulted → Nominal) | Caution attached |
| --- | --- | --- | --- | --- |
| `Aerotech_ABRS_rotary` | yes (motor_homing, alignments) | yes (cold-start home failure → retry) | no | yes ([Aerotech cold-start index miss](cautions.md)) |
| `Sample_top_X` | yes (motor_homing, alignments) | no | no | no |
| `Sample_top_Z` | yes (focus alignment) | no | no | no |
| `Sample_top_Roll` | yes (roll alignment) | no | no | no |
| `Sample_top_Pitch` | yes (pitch alignment) | no | no | no |
| `Optique_Peter_focus_Z` | yes (resolution alignment) | no | no | no |
| `Shutter_2BM` | yes (first_light, baselines) | no | no | no |
| `Oryx_5MP_camera` | yes (resolution, focus, center, roll, pitch, first_light) | no | no | no |
| `Scintillator_LuAG` | yes (resolution, focus, center, roll, pitch, first_light) | no | no | no |
| `Hexapod_2BM` | yes (hexapod_reboot) | no | yes (controller lockup → reboot ceremony) | yes ([Hexapod controller lockup](cautions.md)) |

Lifecycle transitions on Oryx and Scintillator land in every alignment + first-light scenario that consumes the image chain; their condition / Caution facets remain unexercised until further commissioning scenarios surface operator pain points.

## Settings

`Capability.settings_schema` declares the *intrinsic property contract* for a device class (positions, encoder resolution, hardware envelope, per-install calibration). `Asset.settings` carries this specific device's values. Runtime parameters (exposure, energy, rotation step) live on `Method.parameters_schema` instead (Method-side counterpart, separate track).

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

Source of truth: [`test_2bm_alignment_center.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_center.py) (the `_SCHEMA_*` + `_SETTINGS_*` constants near the top of the file) plus the unit-tier coverage at [`tests/unit/equipment/test_pilot_capability_schemas.py`](../../../apps/api/tests/unit/equipment/test_pilot_capability_schemas.py).

## Pending in code

The broader 2-BM Asset stack surfaced by the [2-BM repo survey](https://github.com/xray-imaging/2bm-docs) or `2bmb-bin` IOC scripts. Each lands as a row above when a scenario test (or seed script) registers it.

| Pending Asset | Capability | Role at 2-BM | Source scenario (planned) |
| --- | --- | --- | --- |
| `Mirror_2BM` | (new `Mirror` Capability with coating-dependent energy range) | White-beam mirror with multi-stripe coating (Cr base + Pt / W-Si multilayer / Rh stripes); exercises Asset.replace + Capability re-declaration on substrate return from recoating | `tests/integration/scenarios/test_2bm_mirror_recoat_return.py` |
| `softGlueZynq_FPGA` | (new `TriggerFPGA` Capability) | Hardware trigger generation for fly-scans; needed to model live-reconstruction streaming | Not yet sourced; likely lands with `streaming_tomography` scenario |
| `PCO_Dimax_HS` | `HighSpeedCamera` | High-speed detector alternate to Oryx; used for vibration-baseline acquisitions and continuous-rotation sweeps | Not yet sourced; likely lands with `vibration_baseline` or `continuous_rotation_sweep` |
| Full Optique Peter triple-objective microscope | `LinearStage` x3 (lens swap) + `Scintillator` x3 (per-objective swap) | Three-objective swap stack (Mitutoyo 1.1x / 5x / 10x); exercises Capability re-binding when the operator swaps objectives | Not yet sourced; would land with an operations-phase scan that requires a non-default objective |
| Sample-stage X / Y / Z / pitch / roll motors (broader stack beyond the 5 above) | `LinearStage` (X/Y/Z) + tilt motors | Full sample-stage stack used in mosaic + multi-tile acquisitions | Likely partial coverage from `mosaic_acquisition` scenario |
| IOC-hosted EPICS Devices (8 IOC pairs in `2bmb-bin`) | various | All Devices that need IOC restart cycles to exercise their lifecycle facets | `tests/integration/scenarios/test_2bm_ioc_restart.py` (touches all IOC-hosted Assets in one scenario) |
