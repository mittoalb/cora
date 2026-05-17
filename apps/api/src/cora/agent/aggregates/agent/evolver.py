"""Evolver: replay events to reconstruct Agent state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `AgentEvent` without a matching match arm here.

Status mapping per event type:

  - `AgentDefined`       -> DEFINED    (genesis)
  - `AgentVersioned`     -> VERSIONED  (single-source: Defined only)
  - `AgentDeprecated`    -> DEPRECATED (source: Defined | Versioned |
                                        Suspended)
  - `AgentSuspended`     -> SUSPENDED  (single-source: Versioned only;
                                        Phase 8f-c iter 2)
  - `AgentResumed`       -> VERSIONED  (single-source: Suspended only;
                                        Phase 8f-c iter 2)
  - `AgentToolGranted`   -> status unchanged (additive set mutation;
                                              Phase 8f-c iter 2)
  - `AgentToolRevoked`   -> status unchanged (subtractive set mutation;
                                              Phase 8f-c iter 2)
  - `AgentBudgetRevised` -> status unchanged (budget field replace;
                                              Phase 8f-c iter 2)

Source-state guards live at the decider, NOT here; the evolver trusts
the event log (folded events have already passed their decider).

Transition events applied to empty state raise `ValueError` via the
shared `require_state` helper at `cora.infrastructure.evolver`.

Every arm explicitly carries forward EVERY field of the prior Agent
to guard against the silent-wipe bug caught at the 8f-b iter 1 gate
review (`DecisionLogbookOpened` / `Closed` arms silently wiped
`Decision.ratings`).
"""

from collections.abc import Sequence
from typing import assert_never

from cora.agent.aggregates.agent.events import (
    AgentBudgetRevised,
    AgentDefined,
    AgentDeprecated,
    AgentEvent,
    AgentResumed,
    AgentSuspended,
    AgentToolGranted,
    AgentToolRevoked,
    AgentVersioned,
)
from cora.agent.aggregates.agent.state import (
    Agent,
    AgentBudget,
    AgentCanonicalURI,
    AgentCapability,
    AgentDeprecationReason,
    AgentDescription,
    AgentKind,
    AgentName,
    AgentStatus,
    AgentSuspensionReason,
    AgentVersion,
    ToolName,
)
from cora.infrastructure.evolver import require_state


def evolve(state: Agent | None, event: AgentEvent) -> Agent:
    """Apply one event to the current state."""
    match event:
        case AgentDefined(
            agent_id=agent_id,
            kind=kind,
            name=name,
            version=version,
            model_ref=model_ref,
            description=description,
            canonical_uri=canonical_uri,
            prompt_template_id=prompt_template_id,
            capabilities=capabilities,
            occurred_at=occurred_at,
            tools=tools,
            budget_monthly_usd_cap=budget_monthly_usd_cap,
            budget_daily_token_cap=budget_daily_token_cap,
        ):
            _ = state  # AgentDefined is the genesis event; prior state ignored
            return Agent(
                id=agent_id,
                kind=AgentKind(kind),
                name=AgentName(name),
                version=AgentVersion(version),
                model_ref=model_ref,
                defined_at=occurred_at,
                description=AgentDescription(description) if description is not None else None,
                canonical_uri=(
                    AgentCanonicalURI(canonical_uri) if canonical_uri is not None else None
                ),
                prompt_template_id=prompt_template_id,
                capabilities=frozenset(AgentCapability(c) for c in capabilities),
                status=AgentStatus.DEFINED,
                tools=frozenset(ToolName(t) for t in tools),
                budget=_decode_budget(budget_monthly_usd_cap, budget_daily_token_cap),
            )
        case AgentVersioned(occurred_at=occurred_at):
            prior = require_state(state, "AgentVersioned")
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=prior.name,
                version=prior.version,
                model_ref=prior.model_ref,
                defined_at=prior.defined_at,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=AgentStatus.VERSIONED,
                versioned_at=occurred_at,
                deprecated_at=prior.deprecated_at,
                deprecation_reason=prior.deprecation_reason,
                tools=prior.tools,
                budget=prior.budget,
                suspended_at=prior.suspended_at,
                resumed_at=prior.resumed_at,
                suspension_reason=prior.suspension_reason,
            )
        case AgentDeprecated(reason=reason, occurred_at=occurred_at):
            prior = require_state(state, "AgentDeprecated")
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=prior.name,
                version=prior.version,
                model_ref=prior.model_ref,
                defined_at=prior.defined_at,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=AgentStatus.DEPRECATED,
                versioned_at=prior.versioned_at,
                deprecated_at=occurred_at,
                deprecation_reason=(AgentDeprecationReason(reason) if reason is not None else None),
                tools=prior.tools,
                budget=prior.budget,
                suspended_at=prior.suspended_at,
                resumed_at=prior.resumed_at,
                suspension_reason=prior.suspension_reason,
            )
        case AgentSuspended(reason=reason, occurred_at=occurred_at):
            prior = require_state(state, "AgentSuspended")
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=prior.name,
                version=prior.version,
                model_ref=prior.model_ref,
                defined_at=prior.defined_at,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=AgentStatus.SUSPENDED,
                versioned_at=prior.versioned_at,
                deprecated_at=prior.deprecated_at,
                deprecation_reason=prior.deprecation_reason,
                tools=prior.tools,
                budget=prior.budget,
                suspended_at=occurred_at,
                resumed_at=prior.resumed_at,
                suspension_reason=AgentSuspensionReason(reason),
            )
        case AgentResumed(occurred_at=occurred_at):
            prior = require_state(state, "AgentResumed")
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=prior.name,
                version=prior.version,
                model_ref=prior.model_ref,
                defined_at=prior.defined_at,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=AgentStatus.VERSIONED,
                versioned_at=prior.versioned_at,
                deprecated_at=prior.deprecated_at,
                deprecation_reason=prior.deprecation_reason,
                tools=prior.tools,
                budget=prior.budget,
                # `suspended_at` is preserved as historical audit trail
                # (the agent WAS suspended at that time); `resumed_at`
                # marks the return-to-Versioned moment.
                suspended_at=prior.suspended_at,
                resumed_at=occurred_at,
                # `suspension_reason` is preserved as historical context
                # for the same audit-trail reason. A future re-suspension
                # overwrites it with the fresh reason.
                suspension_reason=prior.suspension_reason,
            )
        case AgentToolGranted(tool_name=tool_name, occurred_at=_):
            prior = require_state(state, "AgentToolGranted")
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=prior.name,
                version=prior.version,
                model_ref=prior.model_ref,
                defined_at=prior.defined_at,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=prior.status,
                versioned_at=prior.versioned_at,
                deprecated_at=prior.deprecated_at,
                deprecation_reason=prior.deprecation_reason,
                tools=prior.tools | {ToolName(tool_name)},
                budget=prior.budget,
                suspended_at=prior.suspended_at,
                resumed_at=prior.resumed_at,
                suspension_reason=prior.suspension_reason,
            )
        case AgentToolRevoked(tool_name=tool_name, occurred_at=_):
            prior = require_state(state, "AgentToolRevoked")
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=prior.name,
                version=prior.version,
                model_ref=prior.model_ref,
                defined_at=prior.defined_at,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=prior.status,
                versioned_at=prior.versioned_at,
                deprecated_at=prior.deprecated_at,
                deprecation_reason=prior.deprecation_reason,
                tools=prior.tools - {ToolName(tool_name)},
                budget=prior.budget,
                suspended_at=prior.suspended_at,
                resumed_at=prior.resumed_at,
                suspension_reason=prior.suspension_reason,
            )
        case AgentBudgetRevised(
            monthly_usd_cap=monthly_usd_cap,
            daily_token_cap=daily_token_cap,
            occurred_at=_,
        ):
            prior = require_state(state, "AgentBudgetRevised")
            return Agent(
                id=prior.id,
                kind=prior.kind,
                name=prior.name,
                version=prior.version,
                model_ref=prior.model_ref,
                defined_at=prior.defined_at,
                description=prior.description,
                canonical_uri=prior.canonical_uri,
                prompt_template_id=prior.prompt_template_id,
                capabilities=prior.capabilities,
                status=prior.status,
                versioned_at=prior.versioned_at,
                deprecated_at=prior.deprecated_at,
                deprecation_reason=prior.deprecation_reason,
                tools=prior.tools,
                budget=_decode_budget(monthly_usd_cap, daily_token_cap),
                suspended_at=prior.suspended_at,
                resumed_at=prior.resumed_at,
                suspension_reason=prior.suspension_reason,
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def _decode_budget(
    monthly_usd_cap: float | None,
    daily_token_cap: int | None,
) -> AgentBudget | None:
    """Build `AgentBudget` from two nullable scalars or return None.

    Both None -> None (cleared budget). At least one non-None ->
    `AgentBudget(monthly_usd_cap, daily_token_cap)`. The VO's
    `__post_init__` validates invariants (no-negatives); a malformed
    payload here would raise `InvalidAgentBudgetError` at replay,
    failing loud rather than silently coercing.
    """
    if monthly_usd_cap is None and daily_token_cap is None:
        return None
    return AgentBudget(monthly_usd_cap=monthly_usd_cap, daily_token_cap=daily_token_cap)


def fold(events: Sequence[AgentEvent]) -> Agent | None:
    """Replay a stream of events from the empty initial state."""
    state: Agent | None = None
    for event in events:
        state = evolve(state, event)
    return state
