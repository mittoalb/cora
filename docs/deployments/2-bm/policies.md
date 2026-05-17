# Policies

*Trust BC boundary shape at 2-BM: the Zone, the Conduit, and the Policies that govern who may issue which command. Per ISA-99 a Zone groups assets with homogeneous trust requirements (orthogonal to the Equipment hierarchy), a Conduit is a governed comms path between Zones, and a Policy is an authorization rule attached to a Conduit. See [Model](../../architecture/model.md) for the aggregate shape.*

## Zone

| Zone | Notes |
| --- | --- |
| `2-BM Zone` | Beamline-scoped trust grouping covering 2-BM Devices, operators, and the Run Debrief agent's interactions with 2-BM Runs |

## Conduit

| Conduit | Endpoints | Notes |
| --- | --- | --- |
| `2-BM Local Conduit` | `2-BM Zone` -> `2-BM Zone` (self-loop) | Single intra-zone communication path. Self-loop because the current scenario corpus does not model cross-zone flows; widens when a second Zone lands (for example a future `Storage Zone` for Dataset publication) |

The Conduit automatically opens a `traversals` observation logbook at creation (per the at-most-one-open-per-kind invariant), so every authorization decision routed through the Conduit accumulates against that logbook for audit.

## Policies

| Policy | Permitted principals | Permitted commands |
| --- | --- | --- |
| `2-BM Operations Policy` | `2-BM Operator 1`, `2-BM Operator 2`, `2-BM Operator 3` (see [Argonne Actors](../argonne/actors.md)) | Operator-driven commands across Equipment, Recipe, Operation, Run, Subject, Dataset, Caution, Clearance, Supply, Campaign (representative list, not exhaustive) |
| `2-BM Agent Policy` | `Run Debrief` (see [Argonne Actors](../argonne/actors.md) and [Agents](../argonne/agents.md)) | Decision-family commands: `RegisterDecision`, `RateDecision`, `AppendReasoningEntry` |

Separating the two policies keeps human-operator and AI-agent authority clean: a new sibling Strategy or Budget agent drops into the Agent Policy without touching the human one, and a new operator role drops into Operations without widening the agent surface.

Source of truth: [`apps/api/tests/integration/scenarios/_facility_fixture.py`](../../../apps/api/tests/integration/scenarios/_facility_fixture.py) (Zone + Conduit + Policy definitions, canonical UUIDs), [`apps/api/tests/integration/scenarios/test_2bm_facility.py`](../../../apps/api/tests/integration/scenarios/test_2bm_facility.py) (end-to-end install assertion).

## How authorization actually runs today

The runtime port wired into tests is `AllowAllAuthorize`, which permits every command unconditionally. The Zone, Conduit, and Policies registered here are therefore declarative shape rather than enforcement: they ground the boundary model in the deployment docs and pre-position the Trust aggregates for the eventual switch to `TrustAuthorize`, where every command issued by a 2-BM operator or the Run Debrief agent will pass through `Policy.evaluate(...)` before any aggregate state mutates.

The `Run Debrief` actor id permitted by the Agent Policy is canonical (`RUN_DEBRIEF_ACTOR_ID` from the fixture). The Agent aggregate itself is registered only by the facility-level install (`test_aps_facility.py`); 2-BM scenarios reference the canonical actor id without re-registering the Agent. This works because Trust BC has no command-time referential integrity (forward-permitted principals are fine), and Run Debrief subscribes facility-wide rather than per-beamline.

## Pending in code

- **A second Zone.** The current self-loop Conduit exists because there is only one Zone at 2-BM. A Storage Zone (for Dataset publication via the deferred `LogbookMirrorPort`) and a Control Zone (for actuation against EPICS IOCs) are the natural next zones; the Conduit and Policy roster widens when either lands.
- **Policy enforcement.** Switching from `AllowAllAuthorize` to `TrustAuthorize` is the trigger for `permitted_commands` lists becoming load-bearing rather than illustrative. The lists today cover the commands the 2-BM scenario corpus exercises but are not exhaustive.
- **Policy status lifecycle.** Per the [Policy aggregate state](../../architecture/model.md), the `Drafted -> Approved -> Active -> Superseded` lifecycle defers to a later sub-phase. Today the Policies are implicit `Active`.
