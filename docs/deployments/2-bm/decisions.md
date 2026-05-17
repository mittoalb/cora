# Decisions

*Decision BC Decisions emitted at 2-BM. A Decision is a structured-audit record of a consequential choice, attributed to a human or agent Actor. The Decision BC's `RunDebrief` agent (see [APS Agents](../aps/agents.md)) emits one advisory Decision per terminal Run. See [Model](../../architecture/model.md) for the aggregate shape.*

*See [Scenarios](../../scenarios/index.md) for the operator routines that exercise this surface.*

| Decision | Context | Choice | Actor | Scenario |
| --- | --- | --- | --- | --- |
| RunDebrief AAR for `Proposal 2026-1234 sample A tomography` | `RunDebrief` | `NominalCompletion` | `Run Debrief` agent | `run_debrief` |
| RunDebrief AAR for `Proposal 2026-1234 sample A tomography (with intervention)` | `RunDebrief` | `DegradedCompletion` | `Run Debrief` agent | `run_debrief_degraded` |
| RunDebrief AAR for `Proposal 2026-1235 sample B tomography (aborted on hexapod fault)` | `RunDebrief` | `EquipmentAbort` | `Run Debrief` agent | `run_debrief_aborted` |
| Operator energy-pivot decision in `Proposal 2026-1237 multi-energy contrast study` | `EnergyChange` | `switch_to_30_keV` | 2-BM Operator | `energy_change` |

Every Decision above carries `confidence_source=self_reported`. RunDebrief Decisions carry `decision_rule=agent:RunDebrief:v1`.

Source of truth: scenario files at [`apps/api/tests/integration/scenarios/test_2bm_<scenario>.py`](../../../apps/api/tests/integration/scenarios/) (one-to-one with the Scenario column).

## Decision choice vocabulary (`RunDebrief` context)

| Choice | Meaning |
| --- | --- |
| `NominalCompletion` | Run reached `Completed` with no operator interventions; output Dataset usable |
| `DegradedCompletion` | Run reached `Completed` with operator intervention (degrade/restore, mid-flight adjust); Dataset usable but flagged for review |
| `OperatorAbort` | Run reached `Aborted` because the operator decided to terminate |
| `EquipmentAbort` | Run reached `Aborted` because Equipment fault forced termination |
| `DataSuspect` | Run reached terminal state but agent narrative review surfaced a data-quality concern |

## Pending in code

| Pending Decision class | Source scenario (planned) |
| --- | --- |
| RunDebrief AAR with `OperatorAbort` choice | Variant of `run_debrief_aborted` distinguished by abort reason (operator judgment, no fault) |
| RunDebrief AAR with `DataSuspect` choice | Lands when scan-quality scoring enters the agent's read scope |
| Manually-triggered re-debrief via `re_debrief_run` slice | Not yet scenario-tier (slice exercised at contract + integration tier) |
| Strategy-agent Decisions (8g sibling to RunDebrief) | Lands with the first non-RunDebrief Agent runtime |
