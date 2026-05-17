# Capabilities

*Equipment BC Capabilities. A Capability names a kind of thing an Asset can do, and is the contract by which a Method declares the device types its realizations need. Capabilities are cross-facility vocabulary, not bound to any Site. See [Model](../architecture/model.md) for the aggregate shape.*

| Capability | Used by Methods |
| --- | --- |
| `RotaryStage` | `center_alignment` |
| `LinearStage` | `center_alignment` |
| `Camera` | `center_alignment` |
| `Scintillator` | `center_alignment` |
| `ProbeGeneric` | `flat_field_correction` |

Source of truth: [`apps/api/tests/integration/test_35bm_beta_alignment_center_scenario.py`](../../apps/api/tests/integration/test_35bm_beta_alignment_center_scenario.py) and [`apps/api/tests/integration/test_aps_install_facility_scenario.py`](../../apps/api/tests/integration/test_aps_install_facility_scenario.py).

## Pending in code

Beamline-typical Capabilities (`HighSpeedCamera`, `Hexapod`, `Goniometer`, `Monochromator`, `Slit`, `Shutter`) are not yet defined. Each lands as a row above when a scenario test or seed script defines it.
