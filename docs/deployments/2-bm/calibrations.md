# Calibrations

*Calibration BC revisions for 2-BM Assets.*

Each Calibration is keyed by `(asset_id, quantity, operating_point)` and carries an append-only revision history. See the [Calibration module](../../architecture/modules/calibration/index.md) for the aggregate shape.

All initial revisions below are `AssertedSource` (operator-attested from vendor datasheets and Optique Peter documentation) with status `Provisional`. Subsequent revisions land as `MeasuredSource` once a calibration Procedure runs.

| Calibration | Target | Quantity | Operating point | Initial value | Source | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `cal_objective_0_mag` | `MCTOptics_objective_0` | `magnification` | `{objective_designation: "10x_Mitutoyo", energy: 25}` | `9.83` | AssertedSource | Provisional |
| `cal_objective_1_mag` | `MCTOptics_objective_1` | `magnification` | `{objective_designation: "5x_Mitutoyo", energy: 25}` | `4.93` | AssertedSource | Provisional |
| `cal_objective_2_mag` | `MCTOptics_objective_2` | `magnification` | `{objective_designation: "1.1x_Mitutoyo", energy: 25}` | `1.10` | AssertedSource | Provisional |
| `cal_scintillator_eff_thickness` | `Scintillator_LuAG` | `effective_thickness` | `{scintillator_material: "LuAG", energy: 25}` | `100 um` | AssertedSource | Provisional |

Magnification values are derived from Optique Peter measured pixel sizes (0.351 / 0.699 / 3.126 micrometer) divided by the Oryx 3.45 micrometer sensor pitch.
