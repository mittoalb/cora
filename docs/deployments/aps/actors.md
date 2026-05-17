# Actors

*Access BC Actors registered at APS by the canonical facility install (`test_aps_facility.py`). These are facility-wide principals: roles that work across any sector or beamline. Per-beamline staff Actors (the 2-BM operator pool, proposal PIs bound to a specific beamtime) live with their beamline. See [Model](../../architecture/model.md) for the aggregate shape.*

*See [Scenarios](../../scenarios/index.md) for the operator routines that exercise this surface.*

| Actor | Kind | Role |
| --- | --- | --- |
| `APS Operator` | `human` | Facility-level operator principal; the canonical "anyone on shift at APS" identity, used by scenarios that are not beamline-specific |
| `Run Debrief` | `agent` | The AI agent co-registered as an Actor by `define_agent` in one atomic cross-BC write (see [Agents](agents.md)); canonical UUID shared with the [2-BM Agent Policy](../2-bm/policies.md) |

Source of truth: [`apps/api/tests/integration/scenarios/test_aps_facility.py`](../../../apps/api/tests/integration/scenarios/test_aps_facility.py) (`RegisterActor(name="APS Operator")` at line 177; the cross-BC atomic Run Debrief Actor + Agent at lines 119-123 / 184-199), [`apps/api/tests/integration/scenarios/_facility_fixture.py`](../../../apps/api/tests/integration/scenarios/_facility_fixture.py) (canonical `RUN_DEBRIEF_ACTOR_ID`).

For the beamline-bound principals these facility-wide rows do NOT cover (operator pool, proposal PIs, review-chain reviewers), see [2-BM Actors](../2-bm/actors.md).

## Pending in code

Additional facility-wide principals (named APS scientific staff with cross-beamline duties, additional sibling Agents beyond `RunDebrief`) are not yet registered. When they land they will be additional rows above.
