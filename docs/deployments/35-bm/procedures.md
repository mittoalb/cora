# Procedures

*Operation BC Procedures registered at 35-BM. See [Model](../../architecture/model.md) for the aggregate shape.*

| Procedure | `kind` | Phase | What it produces |
| --- | --- | --- | --- |
| Motor homing | `motor_homing` | shakedown | Both motors (Aerotech + Sample_top_X) homed and verified |
| Center alignment | `center_alignment` | beta | Calibrated rotation-axis pixel position on the detector |

Source of truth: [`test_35bm_shakedown_motor_homing_scenario.py`](../../../apps/api/tests/integration/test_35bm_shakedown_motor_homing_scenario.py), [`test_35bm_beta_alignment_center_scenario.py`](../../../apps/api/tests/integration/test_35bm_beta_alignment_center_scenario.py).

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

- **Method**: `motor_homing` (Recipe BC, beamline-agnostic; declares `RotaryStage` + `LinearStage_um` capabilities)
- **Practice**: `APS_motor_homing_practice` (Recipe BC, `site_id=APS`)
- **Plan**: `35BM_motor_homing_plan` (Recipe BC, instance-level, no inventory page)
- **Target Assets**: `Aerotech_ABRS_rotary`, `Sample_top_X` (Equipment BC Devices under the 35-BM Unit Asset)
- **Out-of-Procedure side-effects on the Asset stream**: `AssetActivated` x2 (lifecycle), `AssetDegraded` + `AssetRestored` on Aerotech (condition), one `CautionRegistered` on Aerotech

Status FSM: same as Center alignment (`Defined → Running → Completed | Aborted | Truncated`).

Operation stream (4 events per Procedure execution): `ProcedureRegistered → ProcedureStarted → ProcedureStepsLogbookOpened → ProcedureCompleted`.

Per-step entries (9 in total for a typical cold-start with one Aerotech retry): three `Setpoint / Action / Check` triplets, covering Aerotech first attempt (Check fails), Aerotech retry (Check passes), and Sample_top_X (Check passes).

Example queries:

- "Which motors at 35-BM had cold-start home failures?" Filter `Asset` streams for `AssetDegraded` events with `reason LIKE '%cold-start%'`.
- "When was the Aerotech last homed?" Query the `motor_homing` Procedure stream for the most recent `ProcedureCompleted` whose `target_asset_ids` includes the Aerotech.
- "Has anyone documented the Aerotech index-miss?" Query the `CautionLookup` projection for Cautions targeting the Aerotech.

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
- **Practice**: [`35BM_alignment_practice`](../aps/practices.md) (Recipe BC, `site_id=APS`)
- **Plan**: `35BM_center_routine_plan` (Recipe BC, instance-level, no inventory page)
- **Target Assets**: `Aerotech_ABRS_rotary`, `Sample_top_X`, `Oryx_5MP_camera`, `Scintillator_LuAG` (Equipment BC Devices under the 35-BM Unit Asset; full inventory at [Assets](assets.md))

Status FSM: `Defined → Running → Completed | Aborted | Truncated`. The event name `ProcedureRegistered` lands the aggregate in status `Defined` (event-type vs status-name divergence is intentional; status is derived from event type in the evolver).

Operation stream (4 events per Procedure execution):

1. `ProcedureRegistered` (lands in status `Defined`)
2. `ProcedureStarted` (`Defined → Running`)
3. `ProcedureStepsLogbookOpened` (lazy-open on first step append)
4. `ProcedureCompleted` (`Running → Completed`)

Per-step entries land in the `entries_operation_procedure_steps` projection (one row per step), polymorphic by `step_kind ∈ {setpoint, action, check}` with kind-specific payload shape. The Procedure stream records the lifecycle; per-step entries do not emit per-entry events.

Example queries:

- "What was the calibrated rotation-axis pixel position on date X?" Query the Procedure stream for the final Setpoint entry.
- "Which center-alignment routines ran at 35-BM?" Filter Procedures by `kind="center_alignment"`.
- "Which alignments touched the Aerotech rotary stage?" Filter Procedures by `target_asset_id`.
- "How many iterations did this alignment take?" Count Check entries with `iteration` payload keys.

## Pending in code

The four sibling alignment Procedures are not yet registered in code. Each materialises as a row above when its scenario test (or a seed script) registers it. The taxonomy fixes the planned file path per [[project_scenario_taxonomy]]:

| Pending Procedure | Lands when this file ships |
| --- | --- |
| `resolution_alignment` | `apps/api/tests/integration/test_35bm_beta_alignment_resolution_scenario.py` |
| `focus_alignment` | `apps/api/tests/integration/test_35bm_beta_alignment_focus_scenario.py` |
| `roll_alignment` | `apps/api/tests/integration/test_35bm_beta_alignment_roll_scenario.py` |
| `pitch_alignment` | `apps/api/tests/integration/test_35bm_beta_alignment_pitch_scenario.py` |
