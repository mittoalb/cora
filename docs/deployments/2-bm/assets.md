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
| `Sample_top_Roll` | `Device` | `PseudoAxis` | `2-BM` |
| `Sample_top_Pitch` | `Device` | `PseudoAxis` | `2-BM` |
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

## Vendor catalog (Models)

Per-Asset Model bindings carry the vendor identity that PIDINST Property 6 (Manufacturer) and Property 7 (Model) need. Assets bind to a Model at registration; the Asset's Family set must be a subset of the Model's declared families. The four MCTOptics-housing Models (lens turret motor, Mitutoyo MPLAPO objective kit, FLIR Oryx camera, Crytur LuAG scintillator) live on the [MCTOptics deployment](equipment/mctoptics.md#vendor-catalog-models) page; the table below tracks Models bound to non-MCTOptics 2-BM Assets.

| Model | Manufacturer | Part number | Declared Families | Bound at 2-BM |
| --- | --- | --- | --- | --- |
| `aerotech_hexgen_hex300_230hl` | Aerotech | `HEX300-230HL-E1-PL4-TAS` | `Hexapod` | `Hexapod_2BM` |
| `aerotech_abs250mp_m_as` | Aerotech | `ABS250MP-M-AS` | `RotaryStage` | `Aerotech_ABRS_rotary` |
| `aerotech_pro225sl_1000` | Aerotech | `PRO225SL-1000` | `LinearStage` | `Optique_Peter_focus_Z` |
| `kohzu_cyat_070` | Kohzu | `CYAT-070` | `LinearStage` | `Sample_top_X`, `Sample_top_Z` |

Part-number suffix conventions vary by vendor: Aerotech's `HEX300-230HL-E1-PL4-TAS` encodes operationally significant variants (`-E1` incremental encoder, `-PL4` ultra-high-accuracy preload, `-TAS` thermal-actively-stabilized); `ABS250MP-M-AS` follows the same pattern (`-M` mid-precision class, `-AS` air-bearing series); `PRO225SL-1000` carries the `-1000` mm travel suffix natively. v1 stores the full type designation as a single `part_number` string; the catalog convention upgrades to suffix decomposition at the second case where a suffix axis crosses Model boundaries (rule-of-three), or at the first APS imaging stage+drive registration, whichever fires first.

The Aerotech Ensemble HLE10-40-A-MXH drive box (companion to `aerotech_hexgen_hex300_230hl`) and the OMS-VME58 boxes (companions to the Kohzu stages) are intentionally not modelled as separate Assets in v1; whether controllers earn first-class Asset status is tracked in `project_controller_as_asset_research` (Stage-0 seed, deferred-with-trigger).

`Sample_top_Pitch` and `Sample_top_Roll` are PseudoAxis Assets (virtual DoFs over the 2bmHXP hexapod-kinematics solver) and do not bind to a vendor Model. The Model-binding flow (PIDINST) targets physical commissioned hardware; the underlying constituents (the Hexapod_2BM physical axes) carry the Model binding. The remaining four hexapod DoFs (X, Y, Z, Yaw) and the constituent-port wiring from Hexapod_2BM to the virtual DoFs are deferred until the trigger named in `project_pitch_roll_retag`. The Kohzu SA16A-RM goniometer (`Sample_pitch_lam` in the 2-BM source page, possibly the same physical thing as `Sample_top_Pitch` or a third stage) gets its own Model row when the operator-naming question lands.

## Family settings schemas

NEW schemas registered for the 2-BM deployment. The `RotaryStage`, `LinearStage`, `Camera`, and `Scintillator` schemas are declared at the [APS Site assets](../aps/assets.md) level once a second beamline uses them; today they remain implicit in the per-Asset [Settings](#settings) values below. `ImagingDetector` and `PseudoAxis` carry no settings schema (they are presenter / facet Families).

### `Objective`

Intrinsic per-lens properties. Motion is via the lens turret motor wired into the Assembly; this Family declares identity only.

| Setting | Type | Unit | Notes |
| --- | --- | --- | --- |
| `magnification` | number > 0 | dimensionless | covers de-magnification (< 1) for tandem-lens paths |
| `numerical_aperture` | number > 0, &le; 0.95 | dimensionless | synchrotron air-objective ceiling |
| `focal_length` | number > 0 | mm | |
| `working_distance` | number > 0 | mm | |

### `Hexapod`

Operational envelope of a 6-DoF parallel-kinematic positioner. The schema captures the vendor-published envelope (per-DoF travel, speed, resolution, accuracy, load capacity) without exploding the legs as sub-Assets (vendor-sealed unit; inverse kinematics runs in controller firmware, not in CORA). DoF-level addressability (Shape 2: per-DoF PseudoAxis facets referencing this Hexapod as constituent) is a separate design question gated on the Plan.wiring terminal-typing contract.

| Setting | Type | Unit | Notes |
| --- | --- | --- | --- |
| `travel_x` | number > 0 | mm | single-axis from home; translation envelope |
| `travel_y` | number > 0 | mm | |
| `travel_z` | number > 0 | mm | |
| `travel_a` | number > 0 | deg | rotation envelope around X (tilt) |
| `travel_b` | number > 0 | deg | rotation envelope around Y (tilt) |
| `travel_c` | number > 0 | deg | rotation envelope around Z (yaw) |
| `max_speed_translation` | number > 0 | mm/s | typically dominated by the slowest translation axis |
| `max_speed_rotation` | number > 0 | deg/s | typically dominated by the slowest rotation axis |
| `resolution_translation` | number > 0 | nm | encoder resolution for X/Y/Z (vendor reports a common value) |
| `resolution_rotation` | number > 0 | urad | encoder resolution for A/B/C |
| `accuracy_translation` | number > 0 | um | bidirectional positioning accuracy, dominant translation DoF |
| `accuracy_rotation` | number > 0 | urad | bidirectional positioning accuracy, dominant rotation DoF |
| `load_capacity_vertical` | number > 0 | kg | rated load with platform horizontal |
| `load_capacity_horizontal` | number > 0 | kg | rated load with platform vertical |
| `stage_mass` | number > 0 | kg | bare platform mass (excludes mounted payload) |

The pairs `max_speed_translation` / `max_speed_rotation`, `resolution_*`, and `accuracy_*` collapse the six per-DoF measurements down to two values per metric in v1; the vendor datasheet reports per-DoF variation small enough that the dominant-DoF figure is a faithful envelope. When a Method binds against per-DoF setpoints (currently no such Method exists), Shape 2 (PseudoAxis facets) is the surface that grows; the schema above stays as the envelope contract.

## Settings

### `Aerotech_ABRS_rotary`

Bound to Model `aerotech_abs250mp_m_as`. Aerotech ABS250MP-M-AS air-bearing direct-drive rotary stage (250 mm aperture, mid-precision class), driven by an Aerotech Ensemble HLE10-40-A-MXH controller (separate Asset deferred per `project_controller_as_asset_research`).

| Setting | Value |
| --- | --- |
| `min_position` | `−360 deg` |
| `max_position` | `360 deg` |
| `max_speed` | `720 deg/s` |
| `encoder_resolution` | `0.0001 deg` |
| `homing_offset` | `0 deg` |

### `Sample_top_X`

Bound to Model `kohzu_cyat_070`. Kohzu CYAT-070 crossed-roller alignment stage (80 x 80 mm table, ball-screw lead 1.0 mm). Sister Asset `Sample_top_Z` binds the same Model. The full vendor-published envelope (±0.5 um repeatability, lost motion ≤ 2 um, backlash ≤ 1 um, straightness ≤ 3 um per 30 mm, load 98 N, weight 1.7 kg) lives on the [2-BM source page](https://docs2bm.readthedocs.io/en/latest/source/manual/item_020.html); the v1 Settings below capture only the operationally bound min/max/speed/resolution fields.

| Setting | Value |
| --- | --- |
| `min_position` | `−10 mm` |
| `max_position` | `10 mm` |
| `max_speed` | `1 mm/s` |
| `encoder_resolution` | `0.0005 mm` |

### `Hexapod_2BM`

Bound to Model `aerotech_hexgen_hex300_230hl`. Values from the Aerotech HEX300-230HL product datasheet (Hex300-Data-Sheet-D20250203). Per-DoF figures collapse to the dominant axis where the vendor's range across DoFs fits within a faithful envelope (e.g., translation accuracy reported as the laxest of X / Y / Z).

| Setting | Value |
| --- | --- |
| `travel_x` | `55 mm` |
| `travel_y` | `60 mm` |
| `travel_z` | `25 mm` |
| `travel_a` | `15 deg` |
| `travel_b` | `15 deg` |
| `travel_c` | `30 deg` |
| `max_speed_translation` | `25 mm/s` |
| `max_speed_rotation` | `15 deg/s` |
| `resolution_translation` | `20 nm` |
| `resolution_rotation` | `0.2 urad` |
| `accuracy_translation` | `1 um` |
| `accuracy_rotation` | `10 urad` |
| `load_capacity_vertical` | `45 kg` |
| `load_capacity_horizontal` | `21 kg` |
| `stage_mass` | `12 kg` |

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

## Engineering drawings

Each Asset may carry one canonical engineering reference as a `(system, number, revision)` triple per the [Drawing VO](../../architecture/modules/equipment/index.md). The carrier holds the build-to document for the physical specimen; the [Mount drawing](equipment/mctoptics.md#engineering-drawings) on the slot is a separate document (where the slot lives in the beamline). v1 is single-valued; the Drawing-frozenset promotion and `Model.drawing` / `Fixture.drawing` extensions defer to the rule-of-three trigger.

Assets not listed below have no canonical document cited on the 2-BM source page yet (Aerotech `ABS250MP` datasheet for `Aerotech_ABRS_rotary`, Kohzu `CYAT-070` datasheet for the four `Sample_top_*` stages, an APS shutter drawing for `Shutter_2BM`, and a FLIR Oryx datasheet for `Oryx_5MP_camera`). These populate when the operator confirms the canonical reference.

### `Hexapod_2BM`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `Hex300-Data-Sheet` |
| `revision` | `D20250203` |

Aerotech HEX300-230HL hexapod product datasheet (Hex300-Data-Sheet-D20250203.pdf). The MCTOptics deployment cites this as the structured reference for the 6-DoF positioner that anchors the sample stack.

### `Optique_Peter_focus_Z`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

Optique Peter MICRX080 microscope manual (MAN-11863-0521-0465-A, 21 May 2021, 53 pages). The shared vendor manual covers every Optique Peter housing constituent (focus stage, lens turret, lens kit, scintillator). Same reference attaches to each MCTOptics-bound Asset below.

### `MCTOptics_lens_turret`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

### `MCTOptics_objective_0`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

v1 attaches the housing manual as the canonical reference; the Mitutoyo MPLAPO LWD per-magnification datasheet is the eventual upgrade once part numbers are verified (see the [vendor catalog note](equipment/mctoptics.md#vendor-catalog-models) on the Plan-Apo-NIR three-part-number split).

### `MCTOptics_objective_1`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

### `MCTOptics_objective_2`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

### `Scintillator_LuAG`

| Field | Value |
| --- | --- |
| `system` | `EDMS` |
| `number` | `MAN-11863` |
| `revision` | `0521-0465-A` |

## Pending

| Asset | Family |
| --- | --- |
| `Mirror_2BM` | `Mirror` |
| `softGlueZynq_FPGA` | `TriggerFPGA` |
| `PCO_Dimax_HS` | `HighSpeedCamera` |
| Broader sample-stage motors | `LinearStage` + tilt motors |
| IOC-hosted EPICS Devices | |
