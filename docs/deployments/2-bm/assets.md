# Assets

*Equipment BC Assets registered under the 2-BM Unit.*

The Devices that hang off 2-BM. The 2-BM Asset itself sits at the Unit level and is declared on the [2-BM index](index.md). See [Model](../../architecture/model.md) for the aggregate shape.

| Asset | Capability |
| --- | --- |
| `Shutter_2BM` | `Shutter` |
| `Aerotech_ABRS_rotary` | `RotaryStage` |
| `Sample_top_X` | `LinearStage` |
| `Sample_top_Z` | `LinearStage` |
| `Sample_top_Roll` | `LinearStage` |
| `Sample_top_Pitch` | `LinearStage` |
| `Hexapod_2BM` | `Hexapod` |
| `Optique_Peter_focus_Z` | `LinearStage` |
| `Scintillator_LuAG` | `Scintillator` |
| `Oryx_5MP_camera` | `Camera` |

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

| Asset | Capability |
| --- | --- |
| `Mirror_2BM` | `Mirror` |
| `softGlueZynq_FPGA` | `TriggerFPGA` |
| `PCO_Dimax_HS` | `HighSpeedCamera` |
| Optique Peter triple-objective microscope | `LinearStage` ×3 + `Scintillator` ×3 |
| Broader sample-stage motors | `LinearStage` + tilt motors |
| IOC-hosted EPICS Devices | |
