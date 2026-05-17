# Practices

*Recipe BC Practices with `site_id` pointing to the APS Site Asset. A Practice is ISA-88's Site Recipe: the facility-adapted form of a Method. See [Model](../../architecture/model.md) for the aggregate shape.*

| Practice | Method | Purpose |
| --- | --- | --- |
| `APS_standard_flat_field_practice` | [`flat_field_correction`](../../catalog/methods.md) | APS's facility-standard binding of the flat-field correction technique |
| `35BM_alignment_practice` | [`center_alignment`](../../catalog/methods.md) | APS's binding of the `center_alignment` Method against 35-BM's alignment Assets |

Source of truth: [`apps/api/tests/integration/test_aps_install_facility_scenario.py`](../../../apps/api/tests/integration/test_aps_install_facility_scenario.py) and [`apps/api/tests/integration/test_35bm_beta_alignment_center_scenario.py`](../../../apps/api/tests/integration/test_35bm_beta_alignment_center_scenario.py).

## Pending in code

Science-acquisition Practices (Mitutoyo 5× / 50 µm LuAG / 25 keV for phase-contrast fly-scan, and the Mitutoyo 1.1× and 10× variants the Optique Peter microscope supports) are not yet defined in code. Each lands as a row above when a scenario test or seed script defines it.
