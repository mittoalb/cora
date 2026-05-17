Pre-operations routines that ready a beamline for users. The largest cluster today and the one most likely to grow fastest as CORA covers new instruments and modalities. Three sub-groups live here:

- **Alignment chain** (`alignment_resolution` → `alignment_focus` → `alignment_center` → `alignment_roll` → `alignment_pitch`, plus the `alignment_calibration` pre-step). Strict order: each routine depends on the previous one's converged state. All exercise the Operation BC via multi-step Procedures.
- **Equipment bring-up** (`first_light`, `motor_homing`, `hexapod_reboot`). Per-Device readiness routines, including the recovery-from-fault path that walks an Asset through `Faulted → Commissioned` and registers an operator Caution.
- **Detector baselines** (`dark_baseline`, `flat_baseline`). Calibration Datasets registered before any sample acquisition.

When this cluster crosses 15 scenarios, split the three sub-groups into their own pages.
