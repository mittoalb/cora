# MCTOptics at 2-BM

*The Optique Peter detector deployment: one Assembly, one Fixture, six Assets, one virtual axis.*

The MCTOptics detector sits about 55 m from the source in the 2-BM hutch. It is the operator-facing imaging system: a vendor housing that carries three swappable microscope objectives in a turret, a shared focus stage, a single Oryx scientific camera, and a LuAG scintillator. The whole unit is controlled by the [BCDA-APS MCTOptics IOC](https://github.com/BCDA-APS/tomo-bits/blob/main/src/tomo_instrument/devices/mct_optics.py). This page explains how CORA models it.

## The model in one picture

```
2-BM (Unit, Asset)
|
+-- Frame: 2BM_hutch_frame
|     |
|     +-- Mount: optics_mount   ----holds---->   MCTOptics_lens_turret
|                (6-DoF placement)               (rigid mechanical anchor for the housing)
|
+-- Fixture: mctoptics_at_2bm   (surface_id = 2-BM Trust Surface)
|     materializes Assembly = MCTOptics
|     binds 7 slots:
|       objective_0   -> MCTOptics_objective_0   (Asset, Family Objective)
|       objective_1   -> MCTOptics_objective_1   (Asset, Family Objective)
|       objective_2   -> MCTOptics_objective_2   (Asset, Family Objective)
|       camera        -> Oryx_5MP_camera         (Asset, Family Camera)
|       scintillator  -> Scintillator_LuAG       (Asset, Family Scintillator)
|       lens_turret   -> MCTOptics_lens_turret   (Asset, Family RotaryStage)
|       focus         -> Optique_Peter_focus_Z   (Asset, Family LinearStage)
|
+-- MCTOptics_lens_select   (Asset, Family PseudoAxis)
      partition_rule = LookupTable
          0 -> 121.5942 deg  (10x objective in beam)
          1 ->  61.9841 deg  (5x  objective in beam)
          2 ->   2.3006 deg  (1.1x objective in beam)
      constituent_assets = [MCTOptics_lens_turret]
```

Note that `MCTOptics` is the name of the Assembly (the blueprint) and the Fixture (the materialization at 2-BM). It is NOT an Asset row in its own right. The conceptual MCTOptics-the-thing IS the Assembly plus Fixture pair; the physical instance is the seven bound Assets and one PseudoAxis sibling. Seven aggregates participate in the deployment: Assembly, Fixture, Asset, Mount, Frame, Model, Family. The deployment uses all of them.

## Vendor catalog (Models)

Four Models cover the hardware:

| Model | Manufacturer | Part number | Declared Families |
| --- | --- | --- | --- |
| `optique_peter_triple_objective` | Optique Peter | `TripleObj-MCT` | `RotaryStage` |
| `mitutoyo_plan_apo` | Mitutoyo | `Plan-Apo-NIR` | `Objective` |
| `flir_oryx_orx_10g_51s5m_c` | FLIR | `ORX-10G-51S5M-C` | `Camera` |
| `crytur_luag_ce_100um` | Crytur | `LuAG:Ce-100um` | `Scintillator` |

Each Model carries the vendor identity that DOIs and citations need (PIDINST property 7). Assets bind to a Model at registration; the Asset's Family set must be a subset of the Model's declared families.

## Assembly: MCTOptics

The **Assembly** is the reusable composition blueprint. It declares the slot map, the intra-cluster wiring, and which Family the cluster presents as for binding purposes.

| Slot | Cardinality | Required Family |
| --- | --- | --- |
| `objective_0` | `Exactly1` | `Objective` |
| `objective_1` | `Exactly1` | `Objective` |
| `objective_2` | `Exactly1` | `Objective` |
| `camera` | `Exactly1` | `Camera` |
| `scintillator` | `Exactly1` | `Scintillator` |
| `lens_turret` | `Exactly1` | `RotaryStage` |
| `focus` | `Exactly1` | `LinearStage` |

Five intra-cluster wires (slot-keyed, not Asset-keyed):

| Source slot | Source port | Target slot | Target port |
| --- | --- | --- | --- |
| `lens_turret` | `position_feedback_out` | `mctoptics` | `lens_turret_feedback` |
| `mctoptics` | `lens_turret_setpoint` | `lens_turret` | `position_setpoint_in` |
| `mctoptics` | `focus_setpoint` | `focus` | `position_setpoint_in` |
| `focus` | `position_feedback_out` | `mctoptics` | `focus_feedback` |
| `mctoptics` | `camera_trigger` | `camera` | `trigger_in` |

`presents_as_family_id` points at **`ImagingDetector`**, a general Family the Assembly satisfies for any Method that declares `needed_family_ids = {ImagingDetector}`. The Assembly's content hash (SHA-256 over slots + wires + presented Family) is stable: two facilities that publish the same MCTOptics Assembly converge on the same hash, which makes the blueprint cross-facility shareable when the federation layer lands.

## Fixture: MCTOptics at 2-BM

The **Fixture** materializes the Assembly at this specific facility. It records:

- The Assembly id and its content hash (frozen at registration so later Assembly revisions do not silently change this materialization)
- The Trust Surface (`2-BM`) for governance scope
- The slot-to-Asset map binding the 7 named slots to the 7 specific Asset IDs above
- Parameter overrides, if any (none in v1)

A Fixture is single-event genesis: it never changes after registration. To swap a scintillator or replace the camera, the operator decommissions the old Asset, registers the new one, and registers a NEW Fixture against the same Assembly with the updated slot map. The old Fixture stays in the event log as historical record.

Each of the 7 bound Assets carries `fixture_id` back-reference. Operators do not see this field directly; it is a query helper so "which Fixture is this Asset bound into" answers in one lookup.

## Physical placement (Mount + Frame)

The **2BM_hutch_frame** is a named coordinate frame anchored to the hutch's optical table. The **optics_mount** is a named slot on that frame with a 6-DoF placement (translation in mm, rotation in degrees, extrinsic Tait-Bryan). The `MCTOptics_lens_turret` motor is installed into this Mount as the rigid mechanical anchor for the housing: the motor body's position fixes the housing in space, and the objectives, camera, scintillator, and focus stage inherit their position geometrically from the housing's known internal layout. Per-component position tracking is not modelled in v1; if a future calibration campaign needs per-objective offsets, each constituent Asset can get its own Mount at that point.

Where Fixture and Mount fit together: the Fixture answers "what logical cluster lives here for governance," the Mount answers "where in space does this Asset sit." Two orthogonal axes. The Fixture has no placement of its own; only Assets do, via the Mounts they are installed into.

## Routing the lens selector (PseudoAxis)

`MCTOptics_lens_select` is a virtual axis. Its **partition rule** is a closed `LookupTable` decomposing an integer index (0, 1, 2) into a turret rotation in degrees:

| `lens_select` | Turret position | Objective in beam |
| --- | --- | --- |
| `0` | `121.5942 deg` | 10x Mitutoyo |
| `1` | `61.9841 deg` | 5x Mitutoyo |
| `2` | `2.3006 deg` | 1.1x Mitutoyo |

When an operator or Method writes `lens_select = 1`, the Operation BC runtime evaluator pre-expands the command into a setpoint write on the `MCTOptics_lens_turret` constituent. Every actuation is audited as a `controlport.dispatch` event with a correlation id linking back to the PseudoAxis evaluation. The lookup table is event-sourced via `AssetPartitionRuleUpdated`; revising the table (for example, after a turret re-homing campaign) leaves a complete audit trail.

This replaces the older convention of carrying `lens_select` as a Method parameter. The virtual axis is addressable, typed, and audit-complete.

## Calibrations

Four Calibrations downstream of this deployment. Full revision details on the [Calibrations page](../calibrations.md):

- Three `magnification` revisions, one per objective (9.83x / 4.93x / 1.10x effective, derived from measured pixel size divided by sensor pitch)
- One `effective_thickness` revision on the LuAG scintillator (100 micrometers)

All initial revisions are `AssertedSource` (operator-attested from vendor datasheets) with status `Provisional`. They get superseded by `MeasuredSource` revisions when the corresponding calibration Procedure runs.

## PIDINST citation

Two tiers of persistent identifiers:

- **The Fixture earns one DOI** as a citable experimental station. This mirrors the HZB PEAXIS precedent where the composite imaging station is published as a single Instrument with `HasComponent` relations to its parts.
- **Each bound Asset earns its own DOI** (the seven Assets listed above). The Fixture's PIDINST record references them via `HasComponent`; each Asset's record references the Fixture via `IsComponentOf`.

For pilot v1, persistent identifiers are stub-minted (no real DOIs registered with DataCite). The production mint path is deferred until 2-BM commissions with real facility DataCite credentials.

## Operator runbook

**Switch the active objective.** Write the desired `lens_select` index (0, 1, or 2) to the `MCTOptics_lens_select` PseudoAxis. The runtime evaluator looks up the turret position and writes it via the ControlPort. The full chain (operator command, virtual-axis resolution, constituent setpoint) is audited.

**Replace the scintillator.** Decommission `Scintillator_LuAG`, register the replacement Asset (with its own Model binding), then register a new Fixture against the MCTOptics Assembly with the updated `scintillator` slot binding. The Calibration on the new scintillator is a separate `define_calibration` + `append_calibration_revision` ceremony.

**Replace the camera.** Same shape as the scintillator swap: decommission, re-register, new Fixture. The Plan's wiring is unaffected because the Assembly's required wires reference slots, not Asset IDs.

## See also

- [2-BM Assets](../assets.md) for the inventory listing the underlying Asset rows
- [2-BM Calibrations](../calibrations.md) for the four downstream Calibration revisions
- [Equipment module](../../../architecture/modules/equipment/index.md) for the aggregate shapes
- The deployment scenario test at `apps/api/tests/integration/scenarios/test_2bm_mctoptics_setup.py` exercises this ceremony end-to-end
