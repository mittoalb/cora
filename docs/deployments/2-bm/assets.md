# Assets

*Equipment BC Assets registered under the 2-BM Unit.*

The Devices that hang off 2-BM. The 2-BM Asset itself sits at the Unit level and is declared on the [2-BM index](index.md). See [Model](../../architecture/model.md) for the aggregate shape.

The MCTOptics detector is modelled as an Assembly + Fixture pair (not an Asset row in its own right). The constituent Assets appear in the inventory below; the composition and wiring story lives on the dedicated [MCTOptics deployment](equipment/mctoptics.md) page.

## Inventory

| Asset | Level | Family | Parent |
| --- | --- | --- | --- |
| `Shutter_2BM` | `Device` | `Shutter` | `2-BM` |
| `Aerotech_ABRS_rotary` | `Device` | `RotaryStage` | `2-BM` |
| `Sample_top_X` | `Device` | `LinearStage` | `2-BM` |
| `Sample_top_Z` | `Device` | `LinearStage` | `2-BM` |
| `Sample_top_Roll` | `Device` | `LinearStage` | `2-BM` |
| `Sample_top_Pitch` | `Device` | `LinearStage` | `2-BM` |
| `Hexapod_2BM` | `Device` | `Hexapod` | `2-BM` |
| `Optique_Peter_focus_Z` | `Device` | `LinearStage` | `2-BM` (bound into MCTOptics Fixture) |
| `MCTOptics_lens_turret` | `Device` | `RotaryStage` (pending) | `2-BM` (bound into MCTOptics Fixture) |
| `MCTOptics_objective_0` | `Device` | `Objective` | `2-BM` (bound into MCTOptics Fixture) |
| `MCTOptics_objective_1` | `Device` | `Objective` | `2-BM` (bound into MCTOptics Fixture) |
| `MCTOptics_objective_2` | `Device` | `Objective` | `2-BM` (bound into MCTOptics Fixture) |
| `Oryx_5MP_camera` | `Device` | `Camera` | `2-BM` (bound into MCTOptics Fixture) |
| `Scintillator_LuAG` | `Device` | `Scintillator` | `2-BM` (bound into MCTOptics Fixture) |
| `MCTOptics_lens_select` | `Device` | `PseudoAxis` | `2-BM` (bound into MCTOptics Fixture; partition rule decomposes lens index to turret rotation) |

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
| `ImagingDetector` | (empty; this Family exists as the `presents_as_family_id` target for detector Assemblies, including MCTOptics) |
| `Objective` | (pending — empty at initial registration) |
| `PseudoAxis` | (empty; partition rules live on `Asset.partition_rule`, not as affordances) |

`Scintillator` is the lone Pattern-C consumer at v1 (passive optical screen; tracked via `Consumable` lifecycle, no command surface). `ImagingDetector` and `PseudoAxis` are presenter / facet Families: they carry no affordances, but Methods bind against them via `needed_family_ids` (for `ImagingDetector` the Assembly's `presents_as_family_id` is the satisfaction handle; for `PseudoAxis` the Family membership is the gate that lets an Asset carry a `partition_rule`).

## Family settings schemas

NEW schemas registered for the MCTOptics deployment. The `RotaryStage`, `LinearStage`, `Camera`, and `Scintillator` schemas are declared at the [APS Site assets](../aps/assets.md) level. `ImagingDetector` and `PseudoAxis` carry no settings schema (they are presenter / facet Families).

### `Objective`

Intrinsic per-lens properties. Motion is via the lens turret motor wired into the Assembly; this Family declares identity only.

| Setting | Type | Unit | Notes |
| --- | --- | --- | --- |
| `magnification` | number > 0 | dimensionless | covers de-magnification (< 1) for tandem-lens paths |
| `numerical_aperture` | number > 0, &le; 0.95 | dimensionless | synchrotron air-objective ceiling |
| `focal_length` | number > 0 | mm | |
| `working_distance` | number > 0 | mm | |

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

### `MCTOptics_objective_0` (10x)

| Setting | Value |
| --- | --- |
| `magnification` | `10.0` |
| `numerical_aperture` | `0.28` |
| `focal_length` | `20 mm` |
| `working_distance` | `33.5 mm` |

### `MCTOptics_objective_1` (5x)

| Setting | Value |
| --- | --- |
| `magnification` | `5.0` |
| `numerical_aperture` | `0.14` |
| `focal_length` | `40 mm` |
| `working_distance` | `34 mm` |

### `MCTOptics_objective_2` (1.1x)

| Setting | Value |
| --- | --- |
| `magnification` | `1.1` |
| `numerical_aperture` | `0.03` |
| `focal_length` | `200 mm` |
| `working_distance` | `50 mm` |

### `MCTOptics_lens_turret`

`RotaryStage` Family assumed (pending 2-BM operator confirmation; if the turret is a translating slide, the Family flips to `LinearStage` and the signal types switch from `rotation_deg` to `linear_mm`).

| Setting | Value |
| --- | --- |
| `min_position` | `0 deg` |
| `max_position` | `360 deg` |
| `max_speed` | `30 deg/s` |
| `encoder_resolution` | `0.01 deg` |

## Pending

| Asset | Family |
| --- | --- |
| `Mirror_2BM` | `Mirror` |
| `softGlueZynq_FPGA` | `TriggerFPGA` |
| `PCO_Dimax_HS` | `HighSpeedCamera` |
| Broader sample-stage motors | `LinearStage` + tilt motors |
| IOC-hosted EPICS Devices | |
