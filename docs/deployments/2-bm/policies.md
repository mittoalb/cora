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
| `2-BM Operations Policy` | `2-BM Operator 1`, `2-BM Operator 2`, `2-BM Operator 3` (see [2-BM Actors](actors.md)) | Operator-driven commands across Equipment, Recipe, Operation, Run, Subject, Dataset, Caution, Clearance, Supply, Campaign (representative list, not exhaustive) |
| `2-BM Agent Policy` | `Run Debrief` (see [APS Actors](../aps/actors.md) and [APS Agents](../aps/agents.md)) | Decision-family commands: `RegisterDecision`, `RateDecision`, `AppendReasoningEntry` |

Source of truth: [`_facility_fixture.py`](../../../apps/api/tests/integration/scenarios/_facility_fixture.py) (Zone + Conduit + Policy definitions, canonical UUIDs), [`test_2bm_facility.py`](../../../apps/api/tests/integration/scenarios/test_2bm_facility.py) (end-to-end install assertion).

## Enforcement state

The runtime port wired into tests is `AllowAllAuthorize`. The Zone, Conduit, and Policies above are declarative shape, not enforcement; `permitted_commands` lists are illustrative until the switch to `TrustAuthorize`. Policy status is implicit `Active` (the `Drafted → Approved → Active → Superseded` lifecycle defers to a later sub-phase).

## Pending in code

- **A second Zone.** A Storage Zone (for Dataset publication via the deferred `LogbookMirrorPort`) and a Control Zone (for EPICS IOC actuation) are the natural next zones; Conduit and Policy roster widens when either lands.
- **Policy enforcement.** Switching from `AllowAllAuthorize` to `TrustAuthorize` makes `permitted_commands` load-bearing.
- **Policy status lifecycle.** `Drafted → Approved → Active → Superseded` not yet exercised.
