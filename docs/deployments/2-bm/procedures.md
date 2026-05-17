# Procedures

*Operation BC Procedures registered at 2-BM. Each row binds a Method + Practice + Plan to a set of target Assets and runs through the `Defined → Running → Completed | Aborted | Truncated` FSM. Per-step entries (`Setpoint / Action / Check` triplets) land in the `entries_operation_procedure_steps` projection. See [Model](../../architecture/model.md) for the aggregate shape.*

*See [Scenarios](../../scenarios/index.md) for the operator routines that exercise this surface.*

| Procedure | Recipe (Method · Practice) | Target Assets | Side-effects | Scenario |
| --- | --- | --- | --- | --- |
| `motor_homing` | [`motor_homing`](../../catalog/methods.md) · [`APS_motor_homing_practice`](../aps/practices.md) | `Aerotech_ABRS_rotary`, `Sample_top_X` | `AssetActivated` ×2; `AssetDegraded` + `AssetRestored` on Aerotech (cold-start); 1 `CautionRegistered` ([Aerotech cold-start index miss](cautions.md)) | `motor_homing` |
| `first_light` | [`first_light`](../../catalog/methods.md) · [`2BM_first_light_practice`](../aps/practices.md) | `Shutter_2BM`, `Oryx_5MP_camera`, `Scintillator_LuAG` | — | `first_light` |
| `detector_dark_baseline` | [`detector_dark_baseline`](../../catalog/methods.md) · [`2BM_dark_baseline_practice`](../aps/practices.md) | `Shutter_2BM`, `Oryx_5MP_camera`, `Scintillator_LuAG` | 1 `DatasetRegistered` (`NXdark_field`, `subject_id=None`, `producing_run_id=None`) | `dark_baseline` |
| `detector_flat_baseline` | [`detector_flat_baseline`](../../catalog/methods.md) · [`2BM_flat_baseline_practice`](../aps/practices.md) | `Shutter_2BM`, `Oryx_5MP_camera`, `Scintillator_LuAG` | 1 `DatasetRegistered` (`NXflat_field`, same shape as dark) | `flat_baseline` |
| `resolution_alignment` | [`resolution_alignment`](../../catalog/methods.md) · [`2BM_resolution_practice`](../aps/practices.md) | `Optique_Peter_focus_Z`, `Oryx_5MP_camera`, `Scintillator_LuAG` | — | `alignment_resolution` |
| `focus_alignment` | [`focus_alignment`](../../catalog/methods.md) · [`2BM_focus_practice`](../aps/practices.md) | `Sample_top_Z`, `Oryx_5MP_camera`, `Scintillator_LuAG` | — | `alignment_focus` |
| `center_alignment` | [`center_alignment`](../../catalog/methods.md) · [`2BM_alignment_practice`](../aps/practices.md) | `Aerotech_ABRS_rotary`, `Sample_top_X`, `Oryx_5MP_camera`, `Scintillator_LuAG` | — | `alignment_center` |
| `roll_alignment` | [`roll_alignment`](../../catalog/methods.md) · [`2BM_roll_practice`](../aps/practices.md) | `Aerotech_ABRS_rotary`, `Sample_top_Roll`, `Oryx_5MP_camera`, `Scintillator_LuAG` | — | `alignment_roll` |
| `pitch_alignment` | [`pitch_alignment`](../../catalog/methods.md) · [`2BM_pitch_practice`](../aps/practices.md) | `Aerotech_ABRS_rotary`, `Sample_top_Pitch`, `Oryx_5MP_camera`, `Scintillator_LuAG` | — | `alignment_pitch` |
| `alignment_calibration` | `alignment_calibration` · `2BM_alignment_calibration_practice` | `Aerotech_ABRS_rotary`, `Sample_top_Roll`, `Sample_top_Pitch`, `Oryx_5MP_camera`, `Scintillator_LuAG` | — (produces `K_roll` / `K_pitch` as Setpoint entries inside the Procedure log; not first-class CORA state today) | `alignment_calibration` |
| `hexapod_reboot` | [`hexapod_reboot`](../../catalog/methods.md) · `2BM_hexapod_reboot_practice` | `Hexapod_2BM` | `AssetActivated` (first registration), `AssetFaulted` (precondition), `AssetRestored` (postcondition); 1 `CautionRegistered` ([Hexapod controller lockup](cautions.md)) | `hexapod_reboot` |

Source of truth: scenario files at [`apps/api/tests/integration/scenarios/test_2bm_<scenario>.py`](../../../apps/api/tests/integration/scenarios/) (one-to-one with the Scenario column).

Streaming tomography and continuous-rotation acquisitions are Run-level scans, not Procedures. They live on the [Runs page](runs.md) alongside the other operations-phase Runs.

## Per-Procedure step-entry shape

Every Procedure emits the same 4-event Operation stream: `ProcedureRegistered → ProcedureStarted → ProcedureStepsLogbookOpened → ProcedureCompleted`. The step-entry payload count is what varies. Counts below are for the happy-path scenario; entries are polymorphic by `step_kind ∈ {setpoint, action, check}`.

| Procedure | Step entries (happy path) | Notable composition |
| --- | --- | --- |
| `motor_homing` | 9 | three `Setpoint / Action / Check` triplets (Aerotech first attempt fails → Aerotech retry → Sample_top_X) |
| `first_light` | 7 | two `Setpoint / Action / Check` triplets (dark + light) + final `Setpoint(close_shutter, role=return_to_safe_state)` |
| `detector_dark_baseline` | 5 | `Setpoint(verify_closed)` + `Action(acquire_stack)` + `Check(stack_quality)` + `Action(compute_baseline)` + `Check(baseline_quality)` |
| `detector_flat_baseline` | 8 | `Check(sample_out)` + `Setpoint(verify_closed)` + `Setpoint(open)` + `Action(acquire_stack)` + `Check(stack_quality)` + `Setpoint(close)` + `Action(compute_baseline)` + `Check(baseline_quality)` |
| `resolution_alignment` | 13 | four `Setpoint / Action / Check` triplets (initial + 2 outward search + 1 bisection) + final `Setpoint(lock_at_peak)` |
| `focus_alignment` | 13 | same shape as `resolution_alignment` on `Sample_top_Z` |
| `center_alignment` | variable (≥10) | per-iteration `Setpoint(rot=0°) / Action / Check / Setpoint(rot=180°) / Action / Check / Setpoint(X-correction)`; final `Setpoint(RotationCenter=calibrated_px)` |
| `roll_alignment` | 14 (2-iteration converged) | two `Setpoint(rotate_to_0) / Action / Check` triplets per iteration + roll-adjust Setpoint + final `Setpoint(lock_at_calibrated)` |
| `pitch_alignment` | 14 (2-iteration converged) | same shape as `roll_alignment` on `Sample_top_Pitch`; Check on sharpness rather than Y centroid |
| `alignment_calibration` | variable | two per-axis sequences (roll then pitch): baseline-measure → motor-bump → re-measure → motor-restore → compute K; terminated by final `Setpoint(K_<axis>=...)` lock entries |
| `hexapod_reboot` | 17 | five `Setpoint / Action / Check` triplets (IOC stop, PDU off, PDU on, IOC start, enable check) + two standalone `Action(sleep)` entries for settling waits |

## Pending in code

| Pending Procedure | Phase | Source scenario (planned) | Note |
| --- | --- | --- | --- |
| `alignment_auto_chain` | commissioning | `test_2bm_alignment_auto_chain.py` | Full `align auto` orchestration: calibration → Step1 → Step2 (roll) → **Step1 re-run** (roll perturbs tilt) → Step3 → Step4. Campaign-level composition; see [Campaigns](campaigns.md). |
| `energy_calibration` | maintenance | `test_2bm_energy_calibration.py` | Channel-cut-crystal rocking-curve to measure true DMM energy + update offset. Produces a rocking-curve [Dataset](datasets.md). |
| `ioc_restart` | maintenance | `test_2bm_ioc_restart.py` | EPICS IOC bring-up across 8 IOC pairs in `2bmb-bin/*_IOC.sh`; exercises `Asset.degrade → Asset.restore` lifecycle on IOC-hosted Assets + a Supply event for the EPICS subnet. |
| `vibration_baseline` | maintenance | `test_2bm_vibration_baseline.py` | 1000-frame high-speed acquisition before / after APS air-handler shutdown. Produces a vibration-baseline [Dataset](datasets.md); registers a Caution if frequencies exceed reference. |
| `mirror_recoat_return` | maintenance | `test_2bm_mirror_recoat_return.py` | Mirror substrate returns from external recoating; exercises `Asset.replace` + Capability re-declaration. |
