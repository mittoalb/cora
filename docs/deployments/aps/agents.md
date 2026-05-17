# Agents

*Agent BC Agents defined at APS by the canonical facility install. Each Agent's id is shared with an Access BC Actor (kind=agent) via a cross-BC atomic write (`ActorRegistered` + `AgentDefined` in one transaction). See [Model](../../architecture/model.md) for the aggregate shape.*


| Agent | Kind | Version | Model |
| --- | --- | --- | --- |
| `Run Debrief` | `RunDebrief` | `v1` | `anthropic / claude-sonnet-4-6 @ 20251001` |

Source of truth: [`apps/api/tests/integration/scenarios/test_aps_facility.py`](../../../apps/api/tests/integration/scenarios/test_aps_facility.py) (the `define_agent` cross-BC atomic call at lines 184-199 emits `ActorRegistered` + `AgentDefined` in one transaction).

The Trust-side Policy that permits Run Debrief to issue Decision-family commands at 2-BM is the [2-BM Agent Policy](../2-bm/policies.md). New beamlines route their Runs through the same agent identity by adding an analogous Policy in their own deployment folder.

## Pending in code

Sibling Agents (other `kind`s beyond `RunDebrief`) are not yet defined. Each lands as a row above when a scenario test or seed script defines it via `define_agent`.
