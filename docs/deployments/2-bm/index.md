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

- [Assets](assets.md): beamline Devices (Equipment BC), with lifecycle + condition + settings coverage matrix
- [Actors](actors.md): beamline-bound principals (operator pool + proposal PIs + review-chain reviewers); facility-wide principals at [APS Actors](../aps/actors.md)
- [Procedures](procedures.md): operator routines (Operation BC)
- [Subjects](subjects.md): samples (Subject BC) with per-row most-advanced-state
- [Runs](runs.md): Plan executions (Run BC); lifecycle-facets matrix maps each FSM facet to the scenario that exercises it
- [Campaigns](campaigns.md): coordinated studies composing Runs (Campaign BC)
- [Datasets](datasets.md): calibration baselines + per-Run raw projection stacks (Data BC)
- [Decisions](decisions.md): AAR Decisions from the `RunDebrief` agent + operator-authored Decisions (Decision BC)
- [Cautions](cautions.md): operator tribal knowledge on specific Assets (Caution BC)
- [Supplies](supplies.md): beamline-scope continuously-available resources (Supply BC)
- [Policies](policies.md): Trust BC boundary shape (Zone + Conduit + Policies)

The Methods and Practices 2-BM consumes live at higher levels of the hierarchy:

- Methods: cross-facility vocabulary in the [Catalog](../../catalog/methods.md)
- Practices: APS Site Recipes in [APS](../aps/practices.md)

Source of truth: scenario tests at [`apps/api/tests/integration/`](../../../apps/api/tests/integration/) (see [Scenario taxonomy](../../reference/workflow.md#tests) for naming).

For the stakeholder pitch (vision, scope, why this beamline), see the [MAX IV deck](../../talks.md).
