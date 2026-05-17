# Assets

*Equipment BC Assets registered at 35-BM. See [Model](../../architecture/model.md) for the aggregate shape.*

| Asset | Capability | Role at 35-BM |
| --- | --- | --- |
| `Aerotech_ABRS_rotary` | `RotaryStage` | Rotation axis; the motor driven 0° → 180° during alignment iterations and during fly-scan acquisition |
| `Sample_top_X` | `LinearStage` | X-correction motor (Kohzu CYAT-070); the linear stage nudged to close rotation-axis offset |
| `Oryx_5MP_camera` | `Camera` | Alignment-frame detector (FLIR ORX-10G-51S5M-C, 2448 × 2048, 3.45 µm) |
| `Scintillator_LuAG` | `Scintillator` | LuAG scintillator; converts X-rays to visible light for the camera |

Source of truth: [`apps/api/tests/integration/test_35bm_beta_alignment_center_scenario.py`](../../../apps/api/tests/integration/test_35bm_beta_alignment_center_scenario.py) (the four Devices in target role) and [`apps/api/tests/integration/test_35bm_shakedown_motor_homing_scenario.py`](../../../apps/api/tests/integration/test_35bm_shakedown_motor_homing_scenario.py) (lifecycle + condition transitions on the 2 motors).

## Lifecycle and condition coverage

Asset facets exercised in code today (by the two motor Devices):

| Facet | Aerotech | Sample_top_X |
| --- | --- | --- |
| Lifecycle: `Commissioned → Active` | yes (`activate_asset`) | yes (`activate_asset`) |
| Condition: `Nominal → Degraded → Nominal` | yes (degraded on cold-start home failure, restored on retry success) | no (clean homing on first try) |
| Caution attached | yes ([Aerotech cold-start index miss](cautions.md)) | no |

The Oryx camera and LuAG scintillator are passive in motion-control terms; their lifecycle and condition transitions land when a `commissioning` scenario exercises first-light acquisition.

## Pending in code

The broader 35-BM Asset stack (softGlueZynq FPGA, the full Optique Peter triple-objective microscope with three lens / scintillator options, the PCO Dimax HS high-speed detector, sample-stage X/Y/Z/pitch/roll motors, the hexapod) is not yet registered in code. Each lands as a row above when a scenario test or seed script instantiates it.
