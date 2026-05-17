# Decisions

*Decision BC Decisions emitted at 2-BM. A Decision is a structured-audit record of a consequential choice, attributed to a human or agent Actor. The Decision BC's `RunDebrief` agent (see [Argonne Agents](../argonne/agents.md)) emits one advisory Decision per terminal Run. See [Model](../../architecture/model.md) for the aggregate shape.*

| Decision | Context | Choice | Actor | Confidence source |
| --- | --- | --- | --- | --- |
| RunDebrief AAR for `Proposal 2026-1234 sample A tomography` | `RunDebrief` | `NominalCompletion` | `Run Debrief` agent (kind=agent) | `self_reported` |
| RunDebrief AAR for `Proposal 2026-1234 sample A tomography (with intervention)` | `RunDebrief` | `DegradedCompletion` | `Run Debrief` agent (kind=agent) | `self_reported` |
| RunDebrief AAR for `Proposal 2026-1235 sample B tomography (aborted on hexapod fault)` | `RunDebrief` | `EquipmentAbort` | `Run Debrief` agent (kind=agent) | `self_reported` |
| Operator energy-pivot decision in `Proposal 2026-1237 multi-energy contrast study` | `EnergyChange` | `switch_to_30_keV` | 2-BM Operator (kind=human) | `self_reported` |

Source of truth: [`apps/api/tests/integration/scenarios/test_2bm_run_debrief.py`](../../../apps/api/tests/integration/scenarios/test_2bm_run_debrief.py) (happy-path), [`apps/api/tests/integration/scenarios/test_2bm_run_debrief_degraded.py`](../../../apps/api/tests/integration/scenarios/test_2bm_run_debrief_degraded.py) (DegradedCompletion variant), [`apps/api/tests/integration/scenarios/test_2bm_run_debrief_aborted.py`](../../../apps/api/tests/integration/scenarios/test_2bm_run_debrief_aborted.py) (EquipmentAbort variant), [`apps/api/tests/integration/scenarios/test_2bm_energy_change.py`](../../../apps/api/tests/integration/scenarios/test_2bm_energy_change.py) (operator-authored EnergyChange).

## How Decisions get emitted at 2-BM

The [`RunDebrief` agent](../argonne/agents.md) subscribes to terminal Run events (`RunCompleted` / `RunAborted` / `RunStopped` / `RunTruncated`). When a Run reaches a terminal state, the projection-worker framework dispatches the event to the `RunDebriefSubscriber`, which:

1. Loads the Run's context (Subject, Plan, Method, Practice, Cautions, prior Decisions if any).
2. Calls the LLM (via `LLMPort`; `AnthropicLLMAdapter` in production, `FakeLLMAdapter` in CI) with a structured prompt asking for a closed 5-value choice + BLUF + 4-section AAR narrative.
3. Emits `DecisionRegistered` with `context=RunDebrief`, `decision_rule=agent:RunDebrief:v1`, `confidence_source=self_reported`, `actor_id=RUN_DEBRIEF_AGENT_ID` and the deterministically derived Decision id (so retries are no-ops via PG's PK conflict).

The 5-value closed choice vocabulary:

| Choice | Meaning |
| --- | --- |
| `NominalCompletion` | Run reached `Completed` with no operator interventions; output Dataset is usable |
| `DegradedCompletion` | Run reached `Completed` but with operator intervention (degrade/restore cycle, mid-flight Plan adjust); output Dataset usable but flagged for downstream review |
| `OperatorAbort` | Run reached `Aborted` because the operator decided to terminate |
| `EquipmentAbort` | Run reached `Aborted` because Equipment fault forced termination |
| `DataSuspect` | Run reached a terminal state but the agent's narrative review surfaced a data-quality concern that the operator should examine before publishing |

## Rating Decisions (deferred-primary UI)

Per [[project_run_debrief_design]], operators can rate each Decision (`useful` / `misleading` / `ignored`) via the `rate_decision` slice. The latest rating per actor wins. The rating surface is exercised in unit + integration + contract tests; surfacing it on a `decisions/<id>.md` deep-dive page is deferred until the rating UI lands.

## Pending in code

Future Decision shapes surfaced by [[project_run_debrief_design]] watch items or by sibling-agent expansion. Each lands as a row above when a scenario test (or seed script) registers it.

| Pending Decision class | Source scenario (planned) |
| --- | --- |
| RunDebrief AAR for an `OperatorAbort` Run (operator-driven abort with no equipment cause) | Variant scenario in the run_debrief family; differs from `EquipmentAbort` only in the abort reason (operator judgment, no fault) |
| RunDebrief AAR for a `DataSuspect` Run (terminal-completed but flagged for downstream review) | Variant scenario surfacing the fifth `DecisionChoice` value; would land when scan-quality scoring crosses the agent's read scope |
| Manually-triggered re-debrief via `re_debrief_run` slice | Not yet a scenario; the slice is exercised at contract + integration tier. Would land when an operator-triggered re-debrief UX needs end-to-end story |
| Strategy-agent Decisions (sibling to RunDebrief; 8g track per [[project_agent_bc_design]]) | Not yet sourced; would land with the first non-RunDebrief Agent runtime |
