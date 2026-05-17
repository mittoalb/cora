# 35-BM

*APS micro-CT. CORA's first pilot.*

A new dedicated micro-CT instrument at Argonne. White-beam micro-CT moves here from 7-BM.

| Property | Value |
| --- | --- |
| Level | Unit |
| Site | [APS](../aps/index.md) |
| Enterprise | [Argonne](../argonne/index.md) |
| Modality | White-beam micro-CT |
| Status | In design |

## Inventories

What's registered at 35-BM today (Unit level):

- [Assets](assets.md): beamline-owned Devices, with lifecycle and condition transitions
- [Procedures](procedures.md): operator routines (`motor_homing`, `center_alignment`)
- [Cautions](cautions.md): operator tribal knowledge attached to specific Assets
- [Datasets](datasets.md): calibration artifacts produced by commissioning scenarios (dark + flat baselines)

The Methods and Practices 35-BM consumes live at higher levels of the hierarchy:

- Methods: cross-facility vocabulary in the [Catalog](../../catalog/methods.md)
- Practices: APS Site Recipes in [APS](../aps/practices.md)

Source of truth: scenario tests at [`apps/api/tests/integration/`](../../../apps/api/tests/integration/) (see [Scenario taxonomy](../../reference/workflow.md#tests) for naming).

For the stakeholder pitch (vision, scope, why this beamline), see the [MAX IV deck](../../talks.md).
