# Walk

*One scan, end to end. Sample class is provisional pending 35-BM team scoping.*

A representative micro-CT run: a porous rock core for in-situ flow imaging. From mail-in arrival to delivered segmentation. Concrete numbers (objective, energy, frame counts) are illustrative; the workflow shape is not.

## Sample classes targeted

The walk-through uses one provisional class. The full table is filled in with the 35-BM team; each row names the class and what about it stresses CORA.

| Class | Method | Stress |
| --- | --- | --- |
| (TBD) | (TBD) | (TBD) |
| (TBD) | (TBD) | (TBD) |
| (TBD) | (TBD) | (TBD) |

Classes left out on purpose (for example, live-cell imaging, robotic sample handling) will be listed here as explicit non-targets once scoped.

## Walk-through

### 1. Proposal and allocation

The PI submits a proposal through the user portal. A review committee approves it and allocates a 24-hour beamtime window. Both the submission and the allocation are recorded so the eventual scan can always be traced back to the proposal that paid for it. Strategy is interchangeable: review can be a committee vote, an AI-assisted triage, or a hybrid of both.

### 2. Sample receipt

Three rock cores arrive by mail under shipping label `S-042-A/B/C`. Each is registered as a Subject and its custody chain opens. From this moment, the sample is locatable from any of: shipping label, proposal id, or the internal subject id.

### 3. Beamline alignment

Before any science scan, the instrument is aligned against its current Assembly: Mitutoyo 5× objective, 50 µm LuAG scintillator, FLIR Oryx detector. Alignment is itself a Run with its own audit trail, so the rotation axis position, focus, and drift estimate that science scans depend on are themselves auditable. Strategy is interchangeable: scripted alignment or an alignment agent.

### 4. Practice binding

The PI selects the Method *Phase-contrast micro-CT, fly scan*. CORA resolves it against 35-BM's current Assembly into a Practice: *Mitutoyo 5×, 50 µm LuAG, 25 keV, propagation 30 mm*. The Method names the physics; the Practice names this Assembly's realization of it. Swapping the lens or scintillator produces a different Practice for the same Method, without editing the Method.

### 5. Plan

A Plan schedules the Practice against core S-042-A inside the allocated window. The Plan inherits parameter defaults from the Practice (angle count, exposure, sampling pattern) and the PI overrides two: 1801 angles instead of 1501, exposure 8 ms instead of 10 ms. Defaults and overrides are kept separately so the lineage of every parameter is visible.

### 6. Mount

The operator mounts core S-042-A on the rotation stage. CORA records the mount with a reason ("shift-A operator mount"). The binding is reversible: the same subject can later dismount and re-mount on a different stage if needed.

### 7. Fly scan

The scan runs as a single Run. PSO triggers fire from the FPGA at 250 Hz; encoder readings stream continuously into a per-Run telemetry channel that does not flow through the main event log. At the moment the Run starts, CORA snapshots the parameters that were actually in effect (angles, exposure, sampling pattern) and what triggered the start, so months later you can tell what was asked for, separately from what defaults were active that day.

Mid-scan, the operator zooms from 5× to 10× for a region-of-interest pass. CORA records the lens change, refreshes flat-fields against the new optical state, and resumes the same Run without restarting it. Result: 1801 projections, no dropped frames, encoder trace retained.

### 8. Reconstruction with COR

Center-of-rotation finding runs as a Decision against the projection set. The strategy in use here is TomoPy `find_center_vo`, which returns a COR pixel and a confidence estimate. Reconstruction wraps TomoPy as a child Run linked to the scan Run, producing a volume.

The strategy is interchangeable. Swap to `find_center_pc`, an AI probability method, or a manual pick by an operator, and the surrounding workflow does not change. What does change is the strategy named on the Decision, and that record is what makes a swap auditable.

### 9. Denoising

Noise2Inverse360 runs as a deterministic post-processing Run against the reconstructed volume.

### 10. Segmentation

Pore network segmentation runs as a Decision. The strategy here is interactive labeling. Strategy is interchangeable: a trained model or fully manual labeling produces the same kind of result, distinguished only by which strategy is named on the Decision.

### 11. Delivery

Volume, mask, and the event stream that produced them are packaged as a dataset and delivered to the PI. Access is scoped through the original proposal: the PI and co-PIs hold the grant.

## What this exercises

One walk touches every part of the system: proposals and access, sample custody, instrument and alignment, the Method/Practice/Plan/Run ladder, all four interchangeable Decision points (review, alignment, COR, segmentation), the high-rate telemetry channel for encoder data, the four trust zones the data crosses, and a mid-Run equipment change. Re-running the recorded events re-derives the volume, the denoised volume, and the mask, given the same inputs.

The walk is provisional in two ways: the sample class table will be confirmed with the 35-BM team, and details (numbers, lens choices, strategies named) are illustrative.
