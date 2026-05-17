# 2-BM

*APS micro-CT. Operational; mechanically-similar analog that grounds CORA's scenario corpus.*

The bending-magnet micro-CT instrument at APS, hosted under `Sector 2`. CORA's [pilot](../35-bm/index.md) target is 35-BM (greenfield instrument, in design); 2-BM is the operational analog where the recipe ladder, BCs, and trust boundaries get validated against real proposal-driven users today.

| Property | Value |
| --- | --- |
| Asset | `2-BM` (Unit, parent `Sector 2`) |
| Sector | `Sector 2` (Area, under APS) |
| Site | [APS](../aps/index.md) |
| Enterprise | [Argonne](../argonne/index.md) |
| Modality | White-beam micro-CT |
| Status | Operational |

## Inventories

What's registered at 2-BM today (Unit level) per the scenario corpus:

- [Assets](assets.md): beamline-owned Devices, with lifecycle and condition transitions
- [Procedures](procedures.md): operator routines (`motor_homing`, alignment chain, first light, baselines, `hexapod_reboot`, `tomography`; remaining operations + maintenance routines pending)
- [Subjects](subjects.md): samples-or-things being measured (intake genesis + mount + measure cycle exercised; dismount pending)
- [Campaigns](campaigns.md): coordinated studies composing Runs (first proposal Campaign Active with one Run member)
- [Cautions](cautions.md): operator tribal knowledge attached to specific Assets
- [Datasets](datasets.md): calibration artifacts + first Production raw projection stack
- [Decisions](decisions.md): advisory AAR Decisions emitted by the `RunDebrief` agent after every terminal Run

The Methods and Practices 2-BM consumes live at higher levels of the hierarchy:

- Methods: cross-facility vocabulary in the [Catalog](../../catalog/methods.md)
- Practices: APS Site Recipes in [APS](../aps/practices.md)

Source of truth: scenario tests at [`apps/api/tests/integration/`](../../../apps/api/tests/integration/) (see [Scenario taxonomy](../../reference/workflow.md#tests) for naming).

For the stakeholder pitch (vision, scope, why this beamline), see the [MAX IV deck](../../talks.md).
