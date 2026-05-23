# Agents

*Agent BC Agents defined at APS.*

Each Agent's id is shared with an Access BC Actor (`kind=agent`) via a cross-BC atomic write (`ActorRegistered` + `AgentDefined` in one transaction). See [Model](../../architecture/model.md) for the aggregate shape.

| Agent | Kind | Version | Model |
| --- | --- | --- | --- |
| `Run Debrief` | `RunDebriefer` | `v1` | `anthropic / claude-sonnet-4-6 @ 20251001` |

## Pending

| Agent | Kind | Version | Model |
| --- | --- | --- | --- |
| Sibling Agents beyond `RunDebriefer` | | | |
