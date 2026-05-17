# Agents

*Agent BC Agents registered at Argonne. Each Agent's id is shared with an Access BC Actor (kind=agent) via a cross-BC atomic write. See [Model](../../architecture/model.md) for the aggregate shape.*

| Agent | Kind | Version | Model |
| --- | --- | --- | --- |
| `Run Debrief` | `RunDebrief` | `v1` | `anthropic / claude-sonnet-4-6 @ 20251001` |

Source of truth: [`apps/api/tests/integration/test_aps_install_facility_scenario.py`](../../../apps/api/tests/integration/test_aps_install_facility_scenario.py).

## Pending in code

Sibling Agents (other `kind`s beyond `RunDebrief`) are not yet defined. Each lands as a row above when a scenario test or seed script defines it.
