# Assets

*Equipment BC Assets registered **under** the 2-BM Unit (the Devices that hang off it). The 2-BM Asset itself sits at the Unit level and is declared on the [2-BM index](index.md). See [Model](../../architecture/model.md) for the aggregate shape.*

*See [Scenarios](../../scenarios/by-bc.md#equipment) for which operator routines exercise these Assets and what lifecycle facets each one walks through.*

| Asset | Capability | Role at 2-BM |
| --- | --- | --- |
| [`Aerotech_ABRS_rotary`](#aerotech_abrs_rotary) | `RotaryStage` | Rotation axis; the motor driven 0° → 180° during alignment iterations and during fly-scan acquisition |
| [`Sample_top_X`](#sample_top_x) | `LinearStage` | X-correction motor (Kohzu CYAT-070); the linear stage nudged to close rotation-axis offset |
| [`Sample_top_Z`](#sample_top_z) | `LinearStage` | Sample-to-scintillator distance motor (cm range, ~10µm resolution); tunes depth-of-focus and projection magnification together |
| [`Sample_top_Roll`](#sample_top_roll) | `LinearStage` | Roll-tilt motor under the rotation stage; small-angle (milliradian) corrections to keep the rotation axis perpendicular to the camera Y axis |
| [`Sample_top_Pitch`](#sample_top_pitch) | `LinearStage` | Pitch-tilt motor under the rotation stage; orthogonal to Sample_top_Roll; corrects out-of-plane axis tilt (toward/away from camera) |
| [`Optique_Peter_focus_Z`](#optique_peter_focus_z) | `LinearStage` | Focus motor inside the Optique Peter microscope; sub-micron resolution lens-to-scintillator distance |
| [`Shutter_2BM`](#shutter_2bm) | `Shutter` | Safety shutter at the 2-BM front-end; opens to admit beam, closes for safe state |
| [`Oryx_5MP_camera`](#oryx_5mp_camera) | `Camera` | Alignment-frame detector (FLIR ORX-10G-51S5M-C, 2448 × 2048, 3.45 µm) |
| [`Scintillator_LuAG`](#scintillator_luag) | `Scintillator` | LuAG scintillator; converts X-rays to visible light for the camera |
| [`Hexapod_2BM`](#hexapod_2bm) | `Hexapod` | PI sample-positioning hexapod (6-DOF); recoverable via `hexapod_reboot` Procedure when controller locks up |

Each Asset has its own section below with vendor, role, and `Asset.settings` (when the Capability schema is declared). The right-hand table of contents jumps to any Asset directly.

## `Aerotech_ABRS_rotary`

- **Capability** `RotaryStage` (Aerotech ABRS)

| Property | Value | Unit |
| --- | ---: | --- |
| `min_position` | -360 | `deg` |
| `max_position` | 360 | `deg` |
| `max_speed` | 720 | `deg/s` |
| `encoder_resolution` | 0.0001 | `deg` |
| `homing_offset` | 0 | `deg` |

## `Sample_top_X`

- **Capability** `LinearStage` (Kohzu CYAT-070)

| Property | Value | Unit |
| --- | ---: | --- |
| `min_position` | -10 | `mm` |
| `max_position` | 10 | `mm` |
| `max_speed` | 1 | `mm/s` |
| `encoder_resolution` | 0.0005 | `mm` |

## `Sample_top_Z`

- **Capability** `LinearStage`

## `Sample_top_Roll`

- **Capability** `LinearStage`

## `Sample_top_Pitch`

- **Capability** `LinearStage`

## `Optique_Peter_focus_Z`

- **Capability** `LinearStage` (Optique Peter microscope)

## `Shutter_2BM`

- **Capability** `Shutter`

## `Oryx_5MP_camera`

- **Capability** `Camera` (FLIR ORX-10G-51S5M-C)

| Property | Value | Unit |
| --- | ---: | --- |
| `sensor_width` | 2448 | `pixel` |
| `sensor_height` | 2048 | `pixel` |
| `pixel_size` | 3.45 | `um` |
| `bit_depth` | 12 | `bit` |

## `Scintillator_LuAG`

- **Capability** `Scintillator` (LuAG:Ce)

| Property | Value | Unit |
| --- | ---: | --- |
| `thickness` | 100 | `um` |
| `decay_time` | 0.07 | `us` |

## `Hexapod_2BM`

- **Capability** `Hexapod` (PI)

## About Settings

`Capability.settings_schema` declares the *intrinsic property contract* for a Device class (positions, encoder resolution, hardware envelope, per-install calibration). `Asset.settings` carries this specific Device's values. Runtime parameters (exposure, energy, rotation step) live on `Method.parameters_schema` instead (Method-side counterpart, separate track).

Every numeric property carries a `unit: {system, code}` annotation per the [units design](../../architecture/model.md). The same-unit-per-physical-dimension-per-Capability convention means all `RotaryStage` angles are in `deg`, all `LinearStage` lengths in `mm`, etc. Different physical dimensions in the same Capability use different unit codes (positions in `deg` plus `max_speed` in `deg/s`).

Assets without a Settings table do not yet have their `Capability.settings_schema` declared in code; values land here when the schema does.

## Pending

Devices surfaced by the [2-BM repo survey](https://github.com/xray-imaging/2bm-docs) or `2bmb-bin` IOC scripts, not yet present in the inventory above.

- **`Mirror_2BM`** — new `Mirror` Capability (coating-dependent energy range). White-beam mirror with multi-stripe coating (Cr base + Pt / W-Si multilayer / Rh stripes).
- **`softGlueZynq_FPGA`** — new `TriggerFPGA` Capability. Hardware trigger generation for fly-scans; needed to model live-reconstruction streaming.
- **`PCO_Dimax_HS`** — `HighSpeedCamera`. High-speed detector alternate to `Oryx_5MP_camera`; used for vibration-baseline acquisitions and continuous-rotation sweeps.
- **Optique Peter triple-objective microscope (full stack)** — `LinearStage` ×3 (lens swap) + `Scintillator` ×3 (per-objective swap). Three-objective swap stack (Mitutoyo 1.1x / 5x / 10x); exercises Capability re-binding when the operator swaps objectives.
- **Broader sample-stage motors** — `LinearStage` (X / Y / Z) + tilt motors. Full stack used in mosaic and multi-tile acquisitions.
- **IOC-hosted EPICS Devices** — 8 IOC pairs in `2bmb-bin`; all Devices that need IOC restart cycles.
