"""Evolver: replay events to reconstruct Agent state.

Mirror of the other aggregate evolvers. The terminal `assert_never`
case forces pyright (and the runtime) to error if a new event type
is added to `AgentEvent` without a matching match arm here.

Status mapping per event type:

  - `AgentDefined`    -> DEFINED    (genesis)
  - `AgentVersioned`  -> VERSIONED  (single-source: Defined only)
  - `AgentDeprecated` -> DEPRECATED (source: Defined or Versioned)

Source-state guards live at the decider, NOT here; the evolver trusts
the event log (folded events have already passed their decider).

Transition events applied to empty state raise `ValueError` via the
shared `require_state` helper at `cora.infrastructure.evolver`.
"""

from collections.abc import Sequence
from typing import assert_never

from cora.agent.aggregates.agent.events import (
    AgentDefined,
    AgentDeprecated,
    AgentEvent,
    AgentVersioned,
)
from cora.agent.aggregates.agent.state import (
    Agent,
    AgentCanonicalURI,
    AgentCapability,
    AgentDeprecationReason,
    AgentDescription,
    AgentKind,
    AgentName,
    AgentStatus,
    AgentVersion,
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
            )
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def fold(events: Sequence[AgentEvent]) -> Agent | None:
    """Replay a stream of events from the empty initial state."""
    state: Agent | None = None
    for event in events:
        state = evolve(state, event)
    return state
