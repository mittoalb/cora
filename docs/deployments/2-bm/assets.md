# Assets

*Equipment BC Assets registered under the 2-BM Unit.*

The Devices that hang off 2-BM. The 2-BM Asset itself sits at the Unit level and is declared on the [2-BM index](index.md). See [Model](../../architecture/model.md) for the aggregate shape. After the [MCTOptics composition](mctoptics.md) ceremony runs, `Oryx_5MP_camera` and `Scintillator_LuAG` re-parent under `MCTOptics`; their Family + settings stay unchanged.

| Asset | Family | Parent (post-MCTOptics deployment) |
| --- | --- | --- |
| `Shutter_2BM` | `Shutter` | `2-BM` |
| `Aerotech_ABRS_rotary` | `RotaryStage` | `2-BM` |
| `Sample_top_X` | `LinearStage` | `2-BM` |
| `Sample_top_Z` | `LinearStage` | `2-BM` |
| `Sample_top_Roll` | `LinearStage` | `2-BM` |
| `Sample_top_Pitch` | `LinearStage` | `2-BM` |
| `Hexapod_2BM` | `Hexapod` | `2-BM` |
| `Optique_Peter_focus_Z` | `LinearStage` | `2-BM` (wired into `MCTOptics`) |
| `Scintillator_LuAG` | `Scintillator` | `MCTOptics` (re-parented) |
| `Oryx_5MP_camera` | `Camera` | `MCTOptics` (re-parented) |

## Family affordances

Each Family declares a closed-enum set of operational primitives ([Affordances](../../reference/affordances.md)). The set is required at Family definition and replaces wholesale on `version_family`.

| Family | Affordances |
| --- | --- |
| `Shutter` | `Shutterable` |
| `RotaryStage` | `Rotatable`, `Homeable`, `Limitable`, `Following`, `Marking` |
| `LinearStage` | `Translatable`, `Homeable`, `Limitable`, `Following` |
| `Hexapod` | `Posable`, `Homeable`, `Limitable` |
| `Scintillator` | `Consumable` |
| `Camera` | `Imageable`, `Binnable`, `Triggerable`, `Streamable`, `Recording` |

`Scintillator` is the lone Pattern-C consumer at v1 (passive optical screen; tracked via `Consumable` lifecycle, no command surface).

## Settings

### `Aerotech_ABRS_rotary`

| Setting | Value |
| --- | --- |
| `min_position` | `−360 deg` |
| `max_position` | `360 deg` |
| `max_speed` | `720 deg/s` |
| `encoder_resolution` | `0.0001 deg` |
| `homing_offset` | `0 deg` |

### `Sample_top_X`

| Setting | Value |
| --- | --- |
| `min_position` | `−10 mm` |
| `max_position` | `10 mm` |
| `max_speed` | `1 mm/s` |
| `encoder_resolution` | `0.0005 mm` |

### `Scintillator_LuAG`

| Setting | Value |
| --- | --- |
| `thickness` | `100 um` |
| `decay_time` | `0.07 us` |

### `Oryx_5MP_camera`

| Setting | Value |
| --- | --- |
| `sensor_width` | `2448 pixel` |
| `sensor_height` | `2048 pixel` |
| `pixel_size` | `3.45 um` |
| `bit_depth` | `12 bit` |

## Pending

| Asset | Family |
| --- | --- |
| `Mirror_2BM` | `Mirror` |
| `softGlueZynq_FPGA` | `TriggerFPGA` |
| `PCO_Dimax_HS` | `HighSpeedCamera` |
| Optique Peter triple-objective microscope | `LinearStage` ×3 + `Scintillator` ×3 |
| Broader sample-stage motors | `LinearStage` + tilt motors |
| IOC-hosted EPICS Devices | |
