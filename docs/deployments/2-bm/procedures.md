# Procedures

*Operation BC Procedures registered at 2-BM. Each row binds a Method + Practice + Plan to a set of target Assets and runs through the `Defined → Running → Completed | Aborted | Truncated` FSM. Per-step entries (`Setpoint / Action / Check` triplets) land in the `entries_operation_procedure_steps` projection. See [Model](../../architecture/model.md) for the aggregate shape.*

*See [Scenarios](../../scenarios/index.md) for the operator routines that exercise this surface.*

| Procedure | Recipe (Method · Practice) | Target Assets | Scenario |
| --- | --- | --- | --- |
| `motor_homing` | [`motor_homing`](../../catalog/methods.md) · [`APS_motor_homing_practice`](../aps/practices.md) | `Aerotech_ABRS_rotary`, `Sample_top_X` | `motor_homing` |
| `first_light` | [`first_light`](../../catalog/methods.md) · [`2BM_first_light_practice`](../aps/practices.md) | `Shutter_2BM`, `Oryx_5MP_camera`, `Scintillator_LuAG` | `first_light` |
| `detector_dark_baseline` | [`detector_dark_baseline`](../../catalog/methods.md) · [`2BM_dark_baseline_practice`](../aps/practices.md) | `Shutter_2BM`, `Oryx_5MP_camera`, `Scintillator_LuAG` | `dark_baseline` |
| `detector_flat_baseline` | [`detector_flat_baseline`](../../catalog/methods.md) · [`2BM_flat_baseline_practice`](../aps/practices.md) | `Shutter_2BM`, `Oryx_5MP_camera`, `Scintillator_LuAG` | `flat_baseline` |
| `resolution_alignment` | [`resolution_alignment`](../../catalog/methods.md) · [`2BM_resolution_practice`](../aps/practices.md) | `Optique_Peter_focus_Z`, `Oryx_5MP_camera`, `Scintillator_LuAG` | `alignment_resolution` |
| `focus_alignment` | [`focus_alignment`](../../catalog/methods.md) · [`2BM_focus_practice`](../aps/practices.md) | `Sample_top_Z`, `Oryx_5MP_camera`, `Scintillator_LuAG` | `alignment_focus` |
| `center_alignment` | [`center_alignment`](../../catalog/methods.md) · [`2BM_alignment_practice`](../aps/practices.md) | `Aerotech_ABRS_rotary`, `Sample_top_X`, `Oryx_5MP_camera`, `Scintillator_LuAG` | `alignment_center` |
| `roll_alignment` | [`roll_alignment`](../../catalog/methods.md) · [`2BM_roll_practice`](../aps/practices.md) | `Aerotech_ABRS_rotary`, `Sample_top_Roll`, `Oryx_5MP_camera`, `Scintillator_LuAG` | `alignment_roll` |
| `pitch_alignment` | [`pitch_alignment`](../../catalog/methods.md) · [`2BM_pitch_practice`](../aps/practices.md) | `Aerotech_ABRS_rotary`, `Sample_top_Pitch`, `Oryx_5MP_camera`, `Scintillator_LuAG` | `alignment_pitch` |
| `alignment_calibration` | `alignment_calibration` · `2BM_alignment_calibration_practice` | `Aerotech_ABRS_rotary`, `Sample_top_Roll`, `Sample_top_Pitch`, `Oryx_5MP_camera`, `Scintillator_LuAG` | `alignment_calibration` |
| `hexapod_reboot` | [`hexapod_reboot`](../../catalog/methods.md) · `2BM_hexapod_reboot_practice` | `Hexapod_2BM` | `hexapod_reboot` |

Streaming tomography and continuous-rotation acquisitions are Run-level scans, not Procedures. They live on the [Runs page](runs.md) alongside the other operations-phase Runs.

Every Procedure emits the same 4-event Operation stream: `ProcedureRegistered → ProcedureStarted → ProcedureStepsLogbookOpened → ProcedureCompleted`. The number of step entries and the Setpoint / Action / Check shape inside each Procedure vary by routine; for that detail (event counts, side-effects on target Assets, Caution registrations), see the per-scenario stubs under [Scenarios > Commissioning](../../scenarios/commissioning.md).

## Pending

Procedures planned for 2-BM but not yet present in the inventory above.

- **`alignment_auto_chain`** (commissioning) — full `align auto` orchestration: calibration → Step1 → Step2 (roll) → Step1 re-run → Step3 → Step4. Campaign-level composition; see [Campaigns](campaigns.md).
- **`energy_calibration`** (maintenance) — channel-cut-crystal rocking-curve to measure true DMM energy + update offset. Produces a rocking-curve [Dataset](datasets.md).
- **`ioc_restart`** (maintenance) — EPICS IOC bring-up across 8 IOC pairs in `2bmb-bin/*_IOC.sh`; exercises `Asset.degrade → Asset.restore` on IOC-hosted Assets + a Supply event for the EPICS subnet.
- **`vibration_baseline`** (maintenance) — 1000-frame high-speed acquisition before / after APS air-handler shutdown. Produces a vibration-baseline [Dataset](datasets.md); registers a Caution if frequencies exceed reference.
- **`mirror_recoat_return`** (maintenance) — Mirror substrate returns from external recoating; exercises `Asset.replace` + Capability re-declaration.
