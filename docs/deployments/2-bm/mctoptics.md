# MCTOptics

*Optique Peter detector at 2-BM, composed as a Microscope Assembly with 3 Objective + 1 Camera + 1 Scintillator children.*

The MCTOptics vendor unit (the Optique Peter detector at ~55 m from the source, controlled by the [BCDA-APS MCTOptics IOC](https://github.com/BCDA-APS/tomo-bits/blob/main/src/tomo_instrument/devices/mct_optics.py)) houses one FLIR Oryx camera, one LuAG scintillator, and a Triple Objective turret (10x / 5x / 1.1x). In CORA it registers as 6 Assets: a `Microscope`-Family Assembly parent plus 5 Device children, alongside one NEW sibling motor under 2-BM (the lens turret) and reuse of the existing `Optique_Peter_focus_Z` linear stage for shared focus. The existing `Oryx_5MP_camera` and `Scintillator_LuAG` from [Assets](assets.md) are re-parented under MCTOptics rather than re-registered.

The full ceremony is materialized end-to-end in [test_2bm_mctoptics_setup.py](https://github.com/xmap/cora/blob/main/apps/api/tests/integration/scenarios/test_2bm_mctoptics_setup.py); this page mirrors the inventory that ceremony seeds.

## Asset hierarchy

```
2-BM (Unit)
+-- MCTOptics (Assembly, NEW)                      Family: Microscope
|   +-- MCTOptics_objective_0 (Device, NEW)        Family: Objective    10x
|   +-- MCTOptics_objective_1 (Device, NEW)        Family: Objective     5x
|   +-- MCTOptics_objective_2 (Device, NEW)        Family: Objective    1.1x
|   +-- Oryx_5MP_camera (Device, RE-PARENTED)      Family: Camera
|   +-- Scintillator_LuAG (Device, RE-PARENTED)    Family: Scintillator
+-- MCTOptics_lens_turret (Device, NEW sibling)    Family: RotaryStage (pending)
+-- Optique_Peter_focus_Z (Device, pre-existing)   Family: LinearStage
```

## Family registrations

Two NEW Families ship with this composition; the rest reuse the Phase 10e-a locked schemas at [Assets](assets.md).

### `Microscope`

Intrinsic optical-geometry properties of a microscope-detector assembly. Routing controls (lens / camera selection) live OUTSIDE this schema, per the design lock: runtime parameters belong on `Method.parameters_schema`, not on `Family.settings_schema`.

| Setting | Type | Unit |
| --- | --- | --- |
| `camera_objective` | string | - |
| `camera_tube_length` | number | mm |

### `Objective`

Intrinsic per-lens properties. Motion is via the external turret + focus motors wired in through `Plan.wiring`; this Family declares identity only.

| Setting | Type | Unit | Notes |
| --- | --- | --- | --- |
| `magnification` | number > 0 | dimensionless | covers de-magnification (< 1) for tandem-lens paths |
| `numerical_aperture` | number > 0, &le; 0.95 | dimensionless | synchrotron air-objective ceiling |
| `focal_length` | number > 0 | mm | |
| `working_distance` | number > 0 | mm | |

## Per-Asset settings

### `MCTOptics`

| Setting | Value |
| --- | --- |
| `camera_objective` | `"Mitutoyo Plan Apo"` |
| `camera_tube_length` | `200 mm` |

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

`RotaryStage` Family assumed (pending 2-BM operator confirmation; if the turret is a translating slide, the Family flips to `LinearStage` and the signal types below switch from `rotation_deg` to `linear_mm`).

| Setting | Value |
| --- | --- |
| `min_position` | `0 deg` |
| `max_position` | `360 deg` |
| `max_speed` | `30 deg/s` |
| `encoder_resolution` | `0.01 deg` |

### `Oryx_5MP_camera` and `Scintillator_LuAG`

Re-parented as-is from the 2-BM Unit. Settings unchanged from [Assets](assets.md).

## Calibrations

Four `Calibration` revisions keyed by `(asset_id, quantity, operating_point)` per the [Calibration](../../architecture/modules/calibration/index.md) module. All initial revisions are `AssertedSource` (operator-attested from vendor datasheet + Optique Peter doc) with status `Provisional`; subsequent revisions land as `MeasuredSource` once a calibration Procedure runs.

| Calibration | Target | Quantity | Operating point | Initial value |
| --- | --- | --- | --- | --- |
| `cal_objective_0_mag` | `MCTOptics_objective_0` | `magnification` | `{objective_designation: "10x_Mitutoyo", energy: 25}` | `9.83` |
| `cal_objective_1_mag` | `MCTOptics_objective_1` | `magnification` | `{objective_designation: "5x_Mitutoyo", energy: 25}` | `4.93` |
| `cal_objective_2_mag` | `MCTOptics_objective_2` | `magnification` | `{objective_designation: "1.1x_Mitutoyo", energy: 25}` | `1.10` |
| `cal_scintillator_eff_thickness` | `Scintillator_LuAG` | `effective_thickness` | `{scintillator_material: "LuAG", energy: 25}` | `100 um` |

Magnification values derived from Optique Peter doc measured pixel sizes (0.351 / 0.699 / 3.126 micrometer) divided by the Oryx 3.45 micrometer sensor pitch.

## Plan.wiring topology

Five wires connect MCTOptics to its sibling motors and camera child. The `image_out` port on `Oryx_5MP_camera` does NOT terminate at MCTOptics; image data flows to a separate data-pipeline adapter Asset out of scope for this inventory.

| Source | Source port | Target | Target port |
| --- | --- | --- | --- |
| `MCTOptics` | `lens_turret_setpoint` | `MCTOptics_lens_turret` | `position_setpoint_in` |
| `MCTOptics_lens_turret` | `position_feedback_out` | `MCTOptics` | `lens_turret_feedback` |
| `MCTOptics` | `focus_setpoint` | `Optique_Peter_focus_Z` | `position_setpoint_in` |
| `Optique_Peter_focus_Z` | `position_feedback_out` | `MCTOptics` | `focus_feedback` |
| `MCTOptics` | `camera_trigger` | `Oryx_5MP_camera` | `trigger_in` |

Signal-type vocabulary (locked):

- `position_setpoint_rotation_deg` / `position_feedback_rotation_deg`
- `position_setpoint_linear_mm` / `position_feedback_linear_mm`
- `trigger_pulse`
- `image_frame_uri` (opaque URI + checksum; pixel format negotiated by the data-pipeline adapter)

## Operator runbook

### Switch lens

The lens turret is driven by `MCTOptics_lens_turret`. To rotate a different objective into the beam, the operator addresses MCTOptics's `lens_turret_setpoint` port (which the Plan wires to the turret motor). Lens selection at Run time is a Method parameter (`lens_select`, integer 0-2), not a Family setting; see the routing-placement deferral in the deployment lock.

### Swap scintillator

The `Scintillator_LuAG` Asset captures the currently-mounted material. To install a different scintillator (CdWO4, GAGG, ...), register a new Asset with the matching material in its name (e.g., `Scintillator_CdWO4`), re-parent it under MCTOptics, decommission the prior scintillator. A new `effective_thickness` Calibration revision should land for the new material.

### Replace camera

The `Oryx_5MP_camera` Asset is the FLIR Oryx ORX-10G-51S5M-C in the camera bay. If the camera is replaced with a different model, register the new Asset under MCTOptics with the matching Camera Family + settings, decommission the prior camera.

### Verify routing

The current `lens_select` / `camera_select` values are read live from the EPICS PVs by the integration adapter; there is no CORA-side state mirror of them by design. A pre-flight gate validating `Plan.required_routing` against live PV is a deferred Watch item.

## Cross-references

- Composition lock: `mctoptics-2bm-assets-design` (auto-memory)
- Deployment plan: `mctoptics-2bm-deployment-design` (auto-memory)
- Integration test: `apps/api/tests/integration/scenarios/test_2bm_mctoptics_setup.py`
- Spawn-or-fold rule applied: [Equipment module](../../architecture/modules/equipment/index.md#aggregates)
