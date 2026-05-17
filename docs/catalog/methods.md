# Methods

*Recipe BC Methods. A Method names a technique abstractly (ISA-88 General Recipe layer) and declares the Capabilities its realizations must offer. Methods are cross-facility vocabulary, not bound to any Site. See [Model](../architecture/model.md) for the aggregate shape.*

| Method | Needed capabilities | Purpose |
| --- | --- | --- |
| `center_alignment` | `RotaryStage`, `LinearStage`, `Camera`, `Scintillator` | The `center` step in the five-routine rotation-axis alignment chain; iterative 0°/180° convergence on the calibrated rotation-axis pixel position |
| `flat_field_correction` | `ProbeGeneric` | Flat-field (white-field / dark-field) correction baseline applied prior to reconstruction |

Source of truth: [`apps/api/tests/integration/test_35bm_beta_alignment_center_scenario.py`](../../apps/api/tests/integration/test_35bm_beta_alignment_center_scenario.py) and [`apps/api/tests/integration/test_aps_install_facility_scenario.py`](../../apps/api/tests/integration/test_aps_install_facility_scenario.py).

## Pending in code

Science-acquisition Methods (phase-contrast micro-CT fly-scan, nano-CT with FZP, MHz imaging, energy scan, XAS) are not yet defined. Each lands as a row above when a scenario test or seed script registers it.
