# Procedures

*Operation BC Procedures registered at 2-BM. See [Model](../../architecture/model.md) for the aggregate shape.*

| Procedure | `kind` | What it produces |
| --- | --- | --- |
| Motor homing | `motor_homing` | Both motors (Aerotech + Sample_top_X) homed and verified |
| First light | `first_light` | First beam visible on the detector; dark + light + safe-state frames captured |
| Dark baseline | `detector_dark_baseline` | 50-frame dark stack with shutter closed; pixel-wise baseline Dataset for reconstruction subtraction |
| Flat baseline | `detector_flat_baseline` | 50-frame flat stack with shutter open + no sample; pixel-wise baseline Dataset for reconstruction division |
| Resolution alignment | `resolution_alignment` | Focus-Z position at peak image sharpness (Optique Peter focus motor) |
| Focus alignment | `focus_alignment` | Sample-Z position at peak depth-of-focus (Sample_top_Z linear stage) |
| Center alignment | `center_alignment` | Calibrated rotation-axis pixel position on the detector |
| Roll alignment | `roll_alignment` | Rotation axis perpendicular to the camera Y axis (Sample_top_Roll tilt) |
| Pitch alignment | `pitch_alignment` | Rotation axis perpendicular to the beam direction (Sample_top_Pitch tilt) |
| Hexapod reboot | `hexapod_reboot` | Stuck hexapod controller recovered: IOC stop + PDU outlet 4 power-cycle + IOC start + EPICS enable check |
| Alignment calibration | `alignment_calibration` | Motor-sensitivity (`K_roll`) measured empirically before the alignment chain iterates; patches the chain's previously-implicit linear-gain assumption |
| Streaming tomography | `streaming_tomography` | TomoScanStream + tomoStream Run with mid-flight `adjust_run` based on live-reco feedback; first scenario exercising operator-driven parameter steering without abort+restart |
| Continuous-rotation tomography | `continuous_rotation_tomography` | N back-to-back rotation Runs sharing one Plan + Subject under a `Campaign(intent=Series)`; first scenario exercising the Series intent + N-Runs-share-Plan pattern |

Source of truth: [`test_2bm_motor_homing.py`](../../../apps/api/tests/integration/scenarios/test_2bm_motor_homing.py), [`test_2bm_first_light.py`](../../../apps/api/tests/integration/scenarios/test_2bm_first_light.py), [`test_2bm_dark_baseline.py`](../../../apps/api/tests/integration/scenarios/test_2bm_dark_baseline.py), [`test_2bm_flat_baseline.py`](../../../apps/api/tests/integration/scenarios/test_2bm_flat_baseline.py), [`test_2bm_alignment_resolution.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_resolution.py), [`test_2bm_alignment_focus.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_focus.py), [`test_2bm_alignment_center.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_center.py), [`test_2bm_alignment_roll.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_roll.py), [`test_2bm_alignment_pitch.py`](../../../apps/api/tests/integration/scenarios/test_2bm_alignment_pitch.py), [`test_2bm_hexapod_reboot.py`](../../../apps/api/tests/integration/scenarios/test_2bm_hexapod_reboot.py).

## Motor homing

Shakedown of the two motorized Devices (Aerotech rotary, Sample_top_X). Runs without beam, before any alignment Procedure. Registered in code as `kind="motor_homing"`.

### What it produces

Both motors at their reference (home) positions, with encoder counters reset to zero, ready for absolute-coordinate moves. The home outcomes are persisted as `Check` step entries on the Procedure's step log (one Check per motor confirming `index_pulse=1` or `home_limit_switch=asserted`).

### When to run it

Preconditions: motors powered, EPICS IOCs up, motion-control interlocks satisfied, no sample mounted (sample mount blocks rotary range). Cold-start specifically (after power cycle or extended dark period); routine after-shift homes during normal operations don't need this scenario's failure-recovery rhythm.

Comes first in the shakedown phase; everything else (alignment, acquisition) depends on motors knowing where they are.

### How the operator runs it

For each motor:

1. Issue `HOME` command on the motor channel.
2. Trigger `home_motor` action (motion-control performs the home seek).
3. Check the home indicator: `encoder_index_pulse=1` for the rotary (Aerotech), `home_limit_switch=asserted` for the linear (Sample_top_X).
4. If Check fails (Aerotech misses index on cold start, ~1 in 5 attempts): mark the motor as `Degraded`, wait 5s, retry from step 1. On retry success, restore to `Nominal`.
5. Repeat for the next motor.

### Gotchas

- **Aerotech misses index on cold start.** See [Cautions](cautions.md). The first attempt after power-cycle frequently fails to detect the index pulse; subsequent attempts work. Workaround is the one-retry-after-5s pattern encoded in the scenario.
- **Condition transitions are out-of-Procedure but in-narrative.** The operator's degrade/restore decisions are not Procedure step entries; they fire `DegradeAsset` / `RestoreAsset` slices on the Asset stream while the Procedure step log captures the observation that justified the call.

---

### CORA encoding

Bound aggregates:

- **Method**: `motor_homing` (Recipe BC, beamline-agnostic; declares `RotaryStage` + `LinearStage` capabilities)
- **Practice**: `APS_motor_homing_practice` (Recipe BC, `site_id=APS`)
- **Plan**: `2BM_motor_homing_plan` (Recipe BC, instance-level, no inventory page)
- **Target Assets**: `Aerotech_ABRS_rotary`, `Sample_top_X` (Equipment BC Devices under the 2-BM Unit Asset)
- **Out-of-Procedure side-effects on the Asset stream**: `AssetActivated` x2 (lifecycle), `AssetDegraded` + `AssetRestored` on Aerotech (condition), one `CautionRegistered` on Aerotech

Status FSM: same as Center alignment (`Defined → Running → Completed | Aborted | Truncated`).

Operation stream (4 events per Procedure execution): `ProcedureRegistered → ProcedureStarted → ProcedureStepsLogbookOpened → ProcedureCompleted`.

Per-step entries (9 in total for a typical cold-start with one Aerotech retry): three `Setpoint / Action / Check` triplets, covering Aerotech first attempt (Check fails), Aerotech retry (Check passes), and Sample_top_X (Check passes).

Example queries:

- "Which motors at 2-BM had cold-start home failures?" Filter `Asset` streams for `AssetDegraded` events with `reason LIKE '%cold-start%'`.
- "When was the Aerotech last homed?" Query the `motor_homing` Procedure stream for the most recent `ProcedureCompleted` whose `target_asset_ids` includes the Aerotech.
- "Has anyone documented the Aerotech index-miss?" Query the `CautionLookup` projection for Cautions targeting the Aerotech.

## First light

The canonical commissioning milestone: first beam through the optics chain reaches the LuAG scintillator and shows up on the Oryx camera. Registered in code as `kind="first_light"`. Runs once per commissioning campaign (and re-runs as a verification check after long shutdowns).

### What it produces

Three frames captured on the Oryx camera, persisted as `Action(acquire_alignment_frame)` entries on the Procedure's step log:

- A dark frame (shutter closed) confirming the imaging chain is electronically quiet (mean count below ~100).
- A first-light frame (shutter open) confirming beam reached the scintillator (mean count above ~5000).
- A second shutter-closed setpoint returning the chain to safe state.

### When to run it

Preconditions: front-end shutters open, optics chain aligned (the beta-phase alignment chain converged), detector powered and configured, exposure time short enough to avoid scintillator damage on first beam (typically 50 ms).

Sequence in the broader commissioning phase: first-light is the entrance milestone. Subsequent commissioning Procedures (`beam_position_alignment`, `flux_normalization`, `detector_dark_baseline`, `detector_flat_baseline`) assume first-light has succeeded.

### How the operator runs it

Three-frame ceremony at low exposure:

1. Verify the safety shutter is closed. Acquire a dark frame. Confirm mean pixel count is below the darkness threshold (electronics work, no light leak).
2. Open the safety shutter. Acquire the first-light frame. Confirm mean pixel count is above the signal threshold (beam reached the scintillator → camera).
3. Close the safety shutter to return the chain to safe state.

### Gotchas

- **Threshold values are operator tribal knowledge.** "Mean count below 100" / "above 5000" are scintillator + camera dependent. The scenario captures them as Check evidence but does not enforce them.
- **Safety state is implicit.** The dark-light-dark bracket around the acquire frames is a convention; the Procedure does not assert that the shutter is open only during the bracketed acquire. A `safety_invariant` step_kind could enforce this in code (watch item).
- **First-light is non-repeatable.** A given Asset stack only truly has its FIRST first-light once; subsequent runs are re-verifications. The scenario name does not distinguish the two cases.

---

### CORA encoding

Bound aggregates:

- **Method**: [`first_light`](../../catalog/methods.md) (Recipe BC, beamline-agnostic; declares `Shutter` + `Camera` + `Scintillator`)
- **Practice**: [`2BM_first_light_practice`](../aps/practices.md) (Recipe BC, `site_id=APS`)
- **Plan**: `2BM_first_light_plan` (Recipe BC, instance-level)
- **Target Assets**: `Shutter_2BM`, `Oryx_5MP_camera`, `Scintillator_LuAG`

Operation stream (4 events per Procedure execution): `ProcedureRegistered → ProcedureStarted → ProcedureStepsLogbookOpened → ProcedureCompleted`.

Per-step entries (7 in total): two `Setpoint / Action / Check` triplets for the dark and light phases, plus one final `Setpoint(state=closed, role=return_to_safe_state)`.

Example queries:

- "When did 2-BM see first light?" Query the Procedure stream for the earliest `first_light` `ProcedureCompleted` with `passed=True` on the light Check.
- "How has first-light signal level drifted across commissioning campaigns?" Group light-phase Check `actual` values by Procedure date.

## Dark baseline

Acquire a stack of dark frames (shutter closed) and register the pixel-wise baseline as a Dataset for downstream reconstruction to subtract. Registered in code as `kind="detector_dark_baseline"`. Runs after `first_light`, once per commissioning campaign (and refreshed periodically as the detector ages).

### What it produces

A Dataset (HDF5, NeXus `NXdark_field` conforming) containing the pixel-wise dark baseline (mean + std maps across the N-frame stack). Downstream science Runs subtract this baseline from raw projections to remove detector dark current. Lands as `intent=Trial` per the [Data BC design](../../catalog/methods.md); a `promote_dataset` slice (deferred) gates Production.

### When to run it

Preconditions: `first_light` succeeded (proves the imaging chain works), exposure time matches what science projections will use (must be identical for the subtraction to be valid), shutter operational.

The output Dataset is consumed by every subsequent science Run via the reconstruction formula `(raw - dark) / (flat - dark)`. Without it, reconstructions carry the detector's intrinsic offset.

### How the operator runs it

1. Verify the safety shutter is closed.
2. Acquire N dark frames in a single `acquire_dark_stack` burst (typically N=50 at 200 ms each).
3. Compute pixel-wise mean and std across the stack (via `tomopy.misc.morph` or equivalent). Hot pixels surface as outliers in the std map (typically count > 5x median std).
4. Confirm baseline quality (mean near zero detector offset, hot-pixel count below operational limit).
5. Register the resulting baseline as a Dataset.

### Gotchas

- **Exposure must match science.** Dark current scales with exposure time; a baseline acquired at 200 ms cannot be subtracted from 500 ms projections. The Dataset name should encode the exposure to prevent mis-use.
- **N-frame burst is one Action.** The acquire_dark_stack step is a single Procedure entry carrying `n_frames` in params, not N individual Actions. Whether the Action payload should grow a canonical `burst` discriminator is a watch item.
- **Baseline computation is operator-offline.** Mean + std are computed outside CORA and recorded on the Check entry as evidence; the raw frames live in the registered Dataset.

---

### CORA encoding

Bound aggregates:

- **Method**: [`detector_dark_baseline`](../../catalog/methods.md) (Recipe BC, beamline-agnostic; declares `Shutter` + `Camera` + `Scintillator`)
- **Practice**: [`2BM_dark_baseline_practice`](../aps/practices.md) (Recipe BC, `site_id=APS`)
- **Plan**: `2BM_dark_baseline_plan`
- **Target Assets**: `Shutter_2BM`, `Oryx_5MP_camera`, `Scintillator_LuAG`
- **Out-of-Procedure artifact**: one `DatasetRegistered` event with `producing_run_id=None`, `subject_id=None`, `media_type="application/x-hdf5"`, `conforms_to={"https://www.nexusformat.org/NXdark_field"}`.

Operation stream (4 events). Per-step entries: `Setpoint` (verify shutter closed), `Action` (acquire stack), `Check` (stack quality), `Action` (compute baseline), `Check` (baseline quality). Five entries total.

## Flat baseline

Acquire a stack of flat-field frames (shutter open, no sample in beam) and register the pixel-wise baseline as a Dataset for downstream reconstruction to divide by. Registered in code as `kind="detector_flat_baseline"`. Sibling to `detector_dark_baseline`; together they complete the dark + flat pair every CT reconstruction requires.

### What it produces

A Dataset (HDF5, NeXus `NXflat_field` conforming) containing the pixel-wise flat baseline (mean image across the N-frame stack). Captures the incoming beam's spatial profile + scintillator response + camera gain map. Downstream science Runs divide by this baseline (after dark subtraction) to remove multiplicative non-uniformity.

### When to run it

Preconditions: `first_light` succeeded, `detector_dark_baseline` registered (the flat is meaningful only paired with a dark), sample stage retracted so nothing intercepts the beam, exposure matches science. Run before any operations-phase Run that will produce reconstructible data.

### How the operator runs it

1. Operator-asserted Check: sample is OUT of the beam path. CORA cannot verify this in the current model.
2. Verify shutter closed (safe starting state).
3. Open shutter to admit beam.
4. Acquire N flat frames in a single `acquire_flat_stack` burst.
5. Close shutter to return to safe state.
6. Compute pixel-wise mean baseline.
7. Confirm baseline quality (mean near expected beam-flux level, low coefficient-of-variation across pixels).
8. Register the resulting baseline as a Dataset.

### Gotchas

- **"Sample out of beam" is an operator assertion.** Recorded as a Check entry, not verified by CORA. If the sample is partially in the beam, the flat baseline carries sample structure and contaminates every subsequent reconstruction. Whether the Subject BC should model in-beam / out-of-beam status (and gate flat acquisition on it) is a watch item.
- **Dark and flat lineage.** This baseline does not declare `derived_from` even though some pipelines store a dark-subtracted flat. The scenario keeps raw flat separate; a later scenario could register a dark-subtracted-flat with `derived_from` pointing at both baselines.

---

### CORA encoding

Bound aggregates:

- **Method**: [`detector_flat_baseline`](../../catalog/methods.md)
- **Practice**: [`2BM_flat_baseline_practice`](../aps/practices.md)
- **Plan**: `2BM_flat_baseline_plan`
- **Target Assets**: `Shutter_2BM`, `Oryx_5MP_camera`, `Scintillator_LuAG`
- **Out-of-Procedure artifact**: one `DatasetRegistered` event, same shape as dark with `NXflat_field` profile.

Operation stream (4 events). Per-step entries (8 total): `Check` (sample-out assertion), `Setpoint` (verify shutter closed), `Setpoint` (open shutter), `Action` (acquire stack), `Check` (stack quality), `Setpoint` (close shutter), `Action` (compute baseline), `Check` (baseline quality).

## Resolution alignment

The `resolution` step of the rotation-axis alignment chain. Iterative peak-search on the Optique Peter focus-Z motor against a mounted resolution target (Siemens star, USAF 1951, or grating). Registered in code as `kind="resolution_alignment"`. Comes first in the five-routine chain.

### What it produces

The focus-Z motor position at the peak of the image-sharpness curve for the mounted resolution target, persisted as the final `Setpoint(Optique_Peter_focus_Z=peak_mm, role=lock_at_peak)` entry on the Procedure's step log.

### When to run it

Preconditions: a resolution target mounted on the kinematic tip, beam on, focus-Z motor homed and within +/- 100µm of the expected peak (large initial offsets diverge before they converge), exposure time set for adequate signal-to-noise on the target.

Sibling-routine order: `resolution → focus → center → roll → pitch`. Resolution comes first because every downstream routine assumes a sharp image; running them on a defocused frame produces meaningless calibrated values. Operators at mechanically-similar 2-BM run this routine today via the `xray-imaging/adjust` CLI's `resolution` subcommand.

### How the operator runs it

Once the Procedure is started, the operator drives a peak-bracket-and-bisect search:

1. Acquire a baseline frame at the current focus position; measure sharpness via `tomopy.misc.morph` (or per-beamline equivalent).
2. Step focus-Z by +50µm, acquire, measure. If sharper, the peak is in the positive direction; if worse, the peak is bracketed by the prior and current positions.
3. When the peak is bracketed, bisect to the midpoint, acquire, measure. Repeat bisection until the sharpness improvement per step falls under tolerance.
4. Lock focus-Z at the peak.

Typical convergence: 3-4 acquisitions starting within +/- 100µm of the true peak. The sharpness value scale is target-dependent; absolute values are not comparable across resolution targets, only across iterations of the same target.

### Gotchas

- **Sharpness metric is target-dependent.** A Siemens star and a USAF 1951 produce different absolute sharpness values for the same focus position. The scenario records `payload.target` on every Check entry; downstream queries must filter by target before comparing.
- **Peak detection is operator judgment.** The final Check carries `passed=True` when the operator decides the sharpness curve has peaked; there is no enforced numerical convergence criterion. The `evidence.peak_position_mm` payload key captures the operator's claim.
- **Search strategy is captured but not enforced.** The scenario uses bisection (after two outward step-and-search probes); other strategies (golden-section, full grid scan) would be visible as different `role` values on Setpoint entries.

---

### CORA encoding

Bound aggregates:

- **Method**: [`resolution_alignment`](../../catalog/methods.md) (Recipe BC, beamline-agnostic; declares `LinearStage` + `Camera` + `Scintillator`)
- **Practice**: [`2BM_resolution_practice`](../aps/practices.md) (Recipe BC, `site_id=APS`)
- **Plan**: `2BM_resolution_plan` (Recipe BC, instance-level)
- **Target Assets**: `Optique_Peter_focus_Z`, `Oryx_5MP_camera`, `Scintillator_LuAG`

Operation stream (4 events per Procedure execution): `ProcedureRegistered → ProcedureStarted → ProcedureStepsLogbookOpened → ProcedureCompleted`.

Per-step entries (13 in total for a 4-iteration converged search): four `Setpoint / Action / Check` triplets covering initial position, two outward search steps that bracket the peak, and one bisection that lands on the peak; plus one final `Setpoint` to lock focus at the peak position. The scenario carries no `Caution` (no operator pain points surfaced in the happy path); future scenarios may add one if a recurring failure mode appears.

Example queries:

- "What focus-Z peak did 2-BM converge on with a Siemens star?" Filter Procedures by `kind="resolution_alignment"`, then the most recent Check with `passed=True` and `target="siemens_star"`.
- "How tight is the focus tolerance at 2-BM?" Compare `evidence.bracket_low_mm` / `bracket_high_mm` on the bracketing Check entry across recent resolution Procedures.

## Focus alignment

The `focus` step of the rotation-axis alignment chain. Iterative peak-search on the `Sample_top_Z` linear stage to maximize image depth-of-focus for the mounted sample. Registered in code as `kind="focus_alignment"`. Comes second in the five-routine chain, after resolution.

### What it produces

The Sample_top_Z position at peak depth-of-focus for the mounted sample, persisted as the final `Setpoint(Sample_top_Z=peak_mm, role=lock_at_peak)` entry on the Procedure's step log.

### When to run it

Preconditions: sample (or focus phantom) mounted on the kinematic tip, beam on, `resolution_alignment` already converged (the microscope's intrinsic focus must be locked before tuning the sample-Z axis), Sample_top_Z within +/- 1mm of the expected peak.

Distinct from `resolution_alignment`: that routine adjusts the Optique Peter internal lens-to-scintillator distance for the microscope's intrinsic sharpness. This one adjusts the sample-to-scintillator distance, which trades depth-of-focus against magnification. Both end with a Setpoint locking their respective Z motor; together they fix the imaging chain's focus state.

### How the operator runs it

The peak-bracket-and-bisect search shape is the same as resolution alignment, but with ~10x larger step size because the Sample_top_Z range is centimeters and the sharpness curve is broader:

1. Acquire a baseline frame at the current Sample_top_Z; measure sharpness.
2. Step Sample_top_Z by +0.5mm, acquire, measure. If sharper, the peak is in the positive direction; if worse, it is bracketed.
3. When bracketed, bisect to the midpoint, acquire, measure. Repeat until the improvement per step falls under tolerance.
4. Lock Sample_top_Z at the peak.

Typical convergence: 3-4 acquisitions starting within +/- 1mm of the true peak.

### Gotchas

- **Magnification couples with focus on this axis.** Moving Sample_top_Z shifts both depth-of-focus AND projection magnification (the sample-to-detector distance changes the cone-beam geometry). The sharpness Check captures focus quality; the magnification shift is implicit in the Z value and must be accounted for in downstream reconstruction.
- **Sample-Z mount tolerance.** Long Z moves can shift the sample laterally in X / Y due to mounting compliance, falsifying the sharpness measurement. A real procedure may interleave Y / X re-centering after large Z moves; the scenario does not encode this.

---

### CORA encoding

Bound aggregates:

- **Method**: [`focus_alignment`](../../catalog/methods.md) (Recipe BC, beamline-agnostic; declares `LinearStage` + `Camera` + `Scintillator`)
- **Practice**: [`2BM_focus_practice`](../aps/practices.md) (Recipe BC, `site_id=APS`)
- **Plan**: `2BM_focus_plan` (Recipe BC, instance-level)
- **Target Assets**: `Sample_top_Z`, `Oryx_5MP_camera`, `Scintillator_LuAG`

Operation stream (4 events per Procedure execution): `ProcedureRegistered → ProcedureStarted → ProcedureStepsLogbookOpened → ProcedureCompleted`.

Per-step entries (13 in total for a 4-iteration converged search): four `Setpoint / Action / Check` triplets plus one final `Setpoint` locking Z at the peak. Same shape as resolution alignment; differs only in `channel` (`Sample_top_Z` vs `Optique_Peter_focus_Z`), step size, and Check payload key (`sample` vs `target`).

Example queries:

- "What sample-Z did 2-BM converge on for the depth-phantom?" Filter Procedures by `kind="focus_alignment"`, find the most recent Check with `passed=True` and `sample="depth_phantom"`.
- "How does sample-Z peak vary across sample classes?" Group Check entries by `sample` payload key.

## Center alignment

The `center` step of the rotation-axis alignment chain. Iterative 0°/180° convergence on the calibrated rotation-axis pixel position. Registered in code as `kind="center_alignment"`.

### What it produces

A calibrated rotation-axis pixel position on the detector, persisted as the final `Setpoint(RotationCenter=calibrated_px)` entry on the Procedure's step log.

### When to run it

Preconditions: a calibration sphere (or equivalent) mounted on the kinematic tip, beam on, initial misalignment within a few pixels (large initial offsets diverge before they converge).

Sibling-routine order: `resolution → focus → center → roll → pitch`. Center expects resolution and focus to have converged first; running it on a defocused or low-resolution frame produces a calibrated pixel position that is not meaningful. Operators at mechanically-similar 2-BM run this chain today via the `xray-imaging/adjust` CLI.

### How the operator runs it

Once the Procedure is started, the operator drives the iterative convergence loop through Setpoint / Action / Check step entries:

1. Rotate to 0°, acquire, check: `Setpoint(Tomo_Rot=0°)` → `Action(acquire_alignment_frame)` → `Check(centroid_x_px)`.
2. Rotate to 180°, acquire, check with evidence: `Setpoint(Tomo_Rot=180°)` → `Action(acquire_alignment_frame)` → `Check(centroid_x_px)` with `evidence={iteration, offset_px}`.
3. Apply offset correction: `Setpoint(Sample_top_X=-offset_px/2)`.
4. Repeat steps 1-3 until `|offset_px| ≤ tolerance`.
5. Write the calibrated center: `Setpoint(RotationCenter=calibrated_px)`.

Typical convergence: 2-3 iterations starting from a few-pixel misalignment. Tolerance is operator-supplied per run (no enforced default); common practice is `|offset_px| ≤ 0.5`.

### Gotchas

- **Two-namesake-motor problem.** `Sample_top_X` plays two semantic roles in the same loop (the X-correction motor for the rotation-axis offset, and the same physical stage is referenced as `Tomo_Rot` orientation context). The scenario encodes this via a `role` payload key on Setpoint entries; whether AssetPort needs context-dependent identity is an open watch item.
- **Check source is off-line or visual.** The convergence Check is the operator's judgment that sphere centroids match within tolerance. In production this is either a visual call (live tomostream centroid overlay) or an off-line metric (`tomopy.find_center_vo`). The scenario encodes the source via `payload.source ∈ {operator_visual, tomopy_find_center_vo, live_tomostream}` on Check entries.

---

### CORA encoding

Bound aggregates:

- **Method**: [`center_alignment`](../../catalog/methods.md) (Recipe BC, beamline-agnostic)
- **Practice**: [`2BM_alignment_practice`](../aps/practices.md) (Recipe BC, `site_id=APS`)
- **Plan**: `2BM_center_routine_plan` (Recipe BC, instance-level, no inventory page)
- **Target Assets**: `Aerotech_ABRS_rotary`, `Sample_top_X`, `Oryx_5MP_camera`, `Scintillator_LuAG` (Equipment BC Devices under the 2-BM Unit Asset; full inventory at [Assets](assets.md))

Status FSM: `Defined → Running → Completed | Aborted | Truncated`. The event name `ProcedureRegistered` lands the aggregate in status `Defined` (event-type vs status-name divergence is intentional; status is derived from event type in the evolver).

Operation stream (4 events per Procedure execution):

1. `ProcedureRegistered` (lands in status `Defined`)
2. `ProcedureStarted` (`Defined → Running`)
3. `ProcedureStepsLogbookOpened` (lazy-open on first step append)
4. `ProcedureCompleted` (`Running → Completed`)

Per-step entries land in the `entries_operation_procedure_steps` projection (one row per step), polymorphic by `step_kind ∈ {setpoint, action, check}` with kind-specific payload shape. The Procedure stream records the lifecycle; per-step entries do not emit per-entry events.

Example queries:

- "What was the calibrated rotation-axis pixel position on date X?" Query the Procedure stream for the final Setpoint entry.
- "Which center-alignment routines ran at 2-BM?" Filter Procedures by `kind="center_alignment"`.
- "Which alignments touched the Aerotech rotary stage?" Filter Procedures by `target_asset_id`.
- "How many iterations did this alignment take?" Count Check entries with `iteration` payload keys.

## Roll alignment

The `roll` step of the rotation-axis alignment chain. Drives the `Sample_top_Roll` tilt motor (under the rotation stage) until the rotation axis is perpendicular to the camera Y axis, so a fiducial sphere on the axis traces a horizontal line across all rotation angles. Registered in code as `kind="roll_alignment"`. Comes fourth in the five-routine chain.

### What it produces

A calibrated `Sample_top_Roll` angle that makes the rotation axis vertical, persisted as the final `Setpoint(Sample_top_Roll=calibrated_deg, role=lock_at_calibrated)` entry on the Procedure's step log.

### When to run it

Preconditions: calibration sphere mounted on the kinematic tip, beam on, `center_alignment` already converged (so the sphere is on-axis in X; any Y delta between 0° and 180° is then purely a roll-tilt signature, not a centering artifact).

Distinct from `center_alignment`: both use the 0°/180° measurement scheme on the same sphere, but center adjusts `Sample_top_X` against the X centroid and roll adjusts `Sample_top_Roll` against the Y centroid.

### How the operator runs it

Iterative tilt correction:

1. Rotate to 0°, acquire, record sphere centroid Y.
2. Rotate to 180°, acquire, record sphere centroid Y. Compute `delta_y = y_180 - y_0`.
3. If `|delta_y| > tolerance` (typically 0.5 px): adjust `Sample_top_Roll` by `-delta_y / (2 * lever_arm)` degrees, then repeat steps 1-2.
4. When converged, lock the roll motor at the calibrated value.

Typical convergence: 2 iterations from a few-pixel Y delta. The roll motor's angular range is small (sub-degree); steps are milliradians.

### Gotchas

- **Mount tilt vs axis tilt confound.** An off-center mount can produce a Y delta even when the rotation axis is perfectly vertical (mount-induced wobble). Single-fiducial measurement cannot distinguish the two; production routines use multi-fiducial targets or rely on prior center convergence as evidence.
- **Lever-arm calibration is operator tribal knowledge.** The Sample_top_Roll motor's angular step does not map directly to pixels; the conversion depends on sample mount geometry and is captured per-run on the iteration Check as `evidence.lever_arm_mm`.

---

### CORA encoding

Bound aggregates:

- **Method**: [`roll_alignment`](../../catalog/methods.md) (Recipe BC, beamline-agnostic; declares `RotaryStage` + `LinearStage` + `Camera` + `Scintillator`)
- **Practice**: [`2BM_roll_practice`](../aps/practices.md) (Recipe BC, `site_id=APS`)
- **Plan**: `2BM_roll_plan` (Recipe BC, instance-level)
- **Target Assets**: `Aerotech_ABRS_rotary`, `Sample_top_Roll`, `Oryx_5MP_camera`, `Scintillator_LuAG`

Operation stream (4 events per Procedure execution): `ProcedureRegistered → ProcedureStarted → ProcedureStepsLogbookOpened → ProcedureCompleted`.

Per-step entries (14 in total for a 2-iteration converged run): two `Setpoint(rotate_to_0) / Action / Check` triplets bracketing each iteration's 0°/180° measurement, with a roll-adjust Setpoint after the first iteration, and a final `Setpoint(lock_at_calibrated)` on the roll motor.

Example queries:

- "What's 2-BM's current roll calibration?" Query the Procedure stream for the most recent `roll_alignment` with `passed=True`; the final Setpoint carries the calibrated value.
- "How often does roll need re-calibration?" Count completed `roll_alignment` Procedures over time; long gaps imply mechanical stability.

## Pitch alignment

The `pitch` step of the rotation-axis alignment chain. Drives the `Sample_top_Pitch` tilt motor (orthogonal to `Sample_top_Roll`) until the rotation axis is perpendicular to the beam direction, so a fiducial sphere stays at the same depth (and therefore the same focus) across all rotation angles. Registered in code as `kind="pitch_alignment"`. Comes fifth and last in the five-routine chain.

### What it produces

A calibrated `Sample_top_Pitch` angle that removes the out-of-plane rotation-axis tilt, persisted as the final `Setpoint(Sample_top_Pitch=calibrated_deg, role=lock_at_calibrated)` entry on the Procedure's step log.

### When to run it

Preconditions: calibration sphere mounted on the kinematic tip, beam on, `roll_alignment` already converged. Pitch runs last because the Y-centroid signal that roll uses becomes ambiguous in the presence of large pitch errors (the sphere defocuses asymmetrically); roll converges first on a still-pitched axis, then pitch fine-tunes the remaining tilt.

Distinct from `roll_alignment`: both adjust rotation-axis tilt on small-angle motors, but on orthogonal axes. Roll uses the Y-centroid delta between 0° and 180°; pitch uses the image-sharpness delta (a pitch error moves the sphere closer to / further from the scintillator across the rotation, modulating focus).

### How the operator runs it

Iterative tilt correction on sharpness delta:

1. Rotate to 0°, acquire, measure sphere-region sharpness.
2. Rotate to 180°, acquire, measure sphere-region sharpness. Compute `delta_sharpness = sharpness_at_0 - sharpness_at_180`.
3. If `|delta_sharpness| > tolerance` (typically 0.05): adjust `Sample_top_Pitch` by a small angle proportional to `-delta_sharpness`, then repeat steps 1-2.
4. When converged, lock the pitch motor at the calibrated value.

Typical convergence: 2 iterations from ~10% sharpness delta. Motor steps are milliradians; the absolute pitch value after the routine carries the calibration.

### Gotchas

- **Sharpness vs centroid signals are not interchangeable.** Roll and pitch both correct rotation-axis tilt but use different physical quantities (Y centroid in px for roll, sharpness metric for pitch). Downstream queries that look across alignment Procedures cannot treat the Check `actual` values as comparable.
- **Sharpness delta is target-dependent.** Same caveat as `resolution_alignment`: absolute sharpness values vary with the mounted fiducial. The Check records `target` so downstream queries can filter.
- **Order-of-operations encodes domain knowledge.** Pitch-after-roll-after-center is convention, not enforced. A future refinement might add a `requires_completed_kinds` field on Procedure or Method.

---

### CORA encoding

Bound aggregates:

- **Method**: [`pitch_alignment`](../../catalog/methods.md) (Recipe BC, beamline-agnostic; declares `RotaryStage` + `LinearStage` + `Camera` + `Scintillator`)
- **Practice**: [`2BM_pitch_practice`](../aps/practices.md) (Recipe BC, `site_id=APS`)
- **Plan**: `2BM_pitch_plan` (Recipe BC, instance-level)
- **Target Assets**: `Aerotech_ABRS_rotary`, `Sample_top_Pitch`, `Oryx_5MP_camera`, `Scintillator_LuAG`

Operation stream (4 events per Procedure execution): `ProcedureRegistered → ProcedureStarted → ProcedureStepsLogbookOpened → ProcedureCompleted`.

Per-step entries (14 in total for a 2-iteration converged run): same shape as roll alignment, with the Check on sharpness rather than Y centroid, and the adjust setpoint on `Sample_top_Pitch` rather than `Sample_top_Roll`.

Example queries:

- "What's 2-BM's current pitch calibration?" Query the Procedure stream for the most recent `pitch_alignment` with `passed=True`; the final Setpoint carries the calibrated value.
- "Which sphere targets give the cleanest pitch convergence?" Group Check entries by `target` payload key, compare iteration counts.

## Hexapod reboot

Recovery routine for a stuck PI-Hexapod sample-positioning controller: power-cycles PDU outlet 4 and restarts the hexapod EPICS IOC until `2bmHXP:HexapodAllEnabled` reads `1`. Registered in code as `kind="hexapod_reboot"`. Runs reactively (after the operator observes a lockup), never on a schedule.

### What it produces

A stuck hexapod (condition `Faulted`) restored to `Nominal` and producing motion again. The procedure logs 17 step entries documenting the seven-step recovery ceremony (IOC stop, power off, settle, power on, boot, IOC start, EPICS enable check); the Asset stream carries the bracketing `AssetFaulted` (precondition) and `AssetRestored` (postcondition) events. The reboot does not produce a Dataset.

### When to run it

Preconditions: hexapod controller is unresponsive (`2bmHXP:HexapodAllEnabled` stuck at `0`), no other beamline operation is in flight that depends on the hexapod, operator has SSH access to the IOC host (`2bmb@arcturus`) and the PDU credentials in `~/access.json`.

Reactive: runs on first sign of controller unresponsiveness. The [Hexapod controller lockup Caution](cautions.md) surfaces this on every Run start that targets the Hexapod, so operators know the recovery path rather than chasing a phantom motion-control bug.

### How the operator runs it

Source: [`2bmb-bin/hexapod_reboot.py`](https://github.com/xray-imaging/2bmb-bin).

Seven steps, mirrored in the Procedure step entries:

1. Stop hexapod IOC: `hexapod_IOC_stop.sh`.
2. Power OFF PDU outlet 4 (NetBooter HTTP, default PDU `a`).
3. Sleep 10s for controller de-energization.
4. Power ON PDU outlet 4.
5. Sleep 10s for controller boot.
6. Start hexapod IOC: `hexapod_IOC.sh`.
7. Poll `2bmHXP:HexapodAllEnabled.VAL` until it reads `1` (180s timeout). Fallback: if still `0`, `caput 2bmHXP:EnableWork.PROC 1` and re-poll.

The scenario test captures the happy path (controller enabled on first poll); the fallback caput is a watch item for a sibling scenario.

### Gotchas

- **External-system actions are opaque to CORA.** PDU HTTP calls, shell-script invocations, and EPICS CA polls happen outside CORA's spine. The Procedure records them as Action step entries with payload encoding the external call (script name, PV name, outlet number) but cannot independently verify success against the external system.
- **Sleep is a first-class step.** The two 10-second waits are not no-ops; they are operator-enforced controller-settling time. They appear as Action entries with `role=power_settling` / `controller_boot`.
- **PDU credentials are out-of-band.** `~/access.json` holds the NetBooter URL + Basic-auth credentials. The Procedure references the credential set via `pdu="a"` payload key but does not capture the credentials themselves.

---

### CORA encoding

Bound aggregates:

- **Method**: [`hexapod_reboot`](../../catalog/methods.md) (Recipe BC, beamline-agnostic; declares `Hexapod` capability)
- **Practice**: `2BM_hexapod_reboot_practice` (Recipe BC, `site_id=APS`)
- **Plan**: `2BM_hexapod_reboot_plan` (Recipe BC, instance-level)
- **Target Asset**: `Hexapod_2BM` (Equipment BC Device under the 2-BM Unit Asset)
- **Out-of-Procedure side-effects on the Asset stream**: `AssetActivated` (one-time, on first registration), `AssetFaulted` (precondition: operator observed lockup), `AssetRestored` (postcondition: EPICS enable check passed), one `CautionRegistered` capturing the recurring-lockup playbook entry

Operation stream (4 events per Procedure execution): `ProcedureRegistered → ProcedureStarted → ProcedureStepsLogbookOpened → ProcedureCompleted`.

Per-step entries (17 total): five `Setpoint / Action / Check` triplets for the routine reboot steps (15 entries) plus two standalone `Action(sleep)` entries for the two settling waits.

Example queries:

- "How often does the hexapod lock up at 2-BM?" Count `AssetFaulted` events on the Hexapod's Asset stream over a time window.
- "Which reboot attempts needed the fallback `EnableWork` poke?" Filter `hexapod_reboot` Procedure step entries for the `Check` on `HexapodAllEnabled` with `passed=False`, then look for a subsequent `caput` Action with `role=force_enable`. (Today the scenario only captures the happy path; this query lands when the fallback-path scenario ships.)
- "Are operators consistently waiting the full settling time?" Group `Action(sleep)` step entries by `seconds` payload key.

## Pending in code

The following Procedure kinds are surfaced by the [2-BM repo survey](https://github.com/xray-imaging/2bm-docs) but not yet registered in code. Each materializes as a row in the table above when its scenario test (or a seed script) registers it. Planned filenames follow the [scenario naming convention](../../../apps/api/tests/integration/scenarios/README.md):

| Pending Procedure | Phase | Lands when this file ships | Source-of-truth note |
| --- | --- | --- | --- |
| `alignment_auto_chain` | commissioning | `tests/integration/scenarios/test_2bm_alignment_auto_chain.py` | Full `align auto` orchestration: calibration -> Step1 -> Step2 (roll) -> **Step1 re-run** (roll perturbs tilt) -> Step3 -> Step4. Campaign-level composition. See also [Campaigns](campaigns.md). |
| `energy_calibration` | maintenance | `tests/integration/scenarios/test_2bm_energy_calibration.py` | Channel-cut-crystal rocking-curve to measure true DMM energy + update the offset. 7-step Procedure; produces a rocking-curve [Dataset](datasets.md). |
| `ioc_restart` | maintenance | `tests/integration/scenarios/test_2bm_ioc_restart.py` | EPICS IOC bring-up across 8 IOC pairs in `2bmb-bin/*_IOC.sh`; exercises `Asset.degrade` -> `Asset.restore` lifecycle on IOC-hosted Assets + a Supply event for the EPICS subnet. |
| `vibration_baseline` | maintenance | `tests/integration/scenarios/test_2bm_vibration_baseline.py` | 1000-frame high-speed acquisition to characterize vertical vibration before / after APS air-handler shutdown. Produces a vibration-baseline [Dataset](datasets.md); registers a Caution if frequencies exceed reference. |
| `mirror_recoat_return` | maintenance | `tests/integration/scenarios/test_2bm_mirror_recoat_return.py` | Mirror substrate returns from external recoating (Cr base + Pt / W-Si multilayer / Rh stripes); re-install + re-commission. Exercises Asset.replace (Mirror) and Capability re-declaration (coating stripes change usable energy ranges). |
