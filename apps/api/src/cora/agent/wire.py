"""Compose the Agent BC's handlers from `Kernel`.

`wire_agent(deps)` is invoked once from the FastAPI lifespan and
the returned `AgentHandlers` bundle is stored on
`app.state.agent`. Routes and MCP tools pull their handler out of
that bundle. New slices add a new field on `AgentHandlers` and a
single line in this factory.

Cross-cutting decorators applied here mirror Access / Trust /
Subject / Equipment / Supply / Safety / Caution:

  1. `bind(deps)` -- bare handler.
  2. `with_idempotency` (create-style commands only) -- Idempotency-
     Key support. Wrapped before tracing so cache-hits and cache-
     misses both attribute to the tracing span.
  3. `with_tracing` -- OTel span around every handler call.

## Wired handlers (8f-c iter 2)

  - `define_agent`            (cross-BC atomic; create-style;
                               idempotency-wrapped)
  - `version_agent`           (transition; no idempotency wrap)
  - `deprecate_agent`         (transition; no idempotency wrap)
  - `suspend_agent`           (transition; no idempotency wrap)
  - `resume_agent`            (transition; no idempotency wrap)
  - `grant_tool_to_agent`     (transition; idempotent; no wrap)
  - `revoke_tool_from_agent`  (transition; idempotent; no wrap)
  - `revise_agent_budget`     (transition; idempotent; no wrap)
  - `get_agent`               (query)
  - `re_debrief_run`          (operator-triggered; idempotency-wrapped)
"""

from dataclasses import dataclass
from uuid import UUID

from cora.agent.features import (
    define_agent,
    deprecate_agent,
    get_agent,
    grant_tool_to_agent,
    promote_caution_proposal,
    re_debrief_run,
    resume_agent,
    revise_agent_budget,
    revoke_tool_from_agent,
    suspend_agent,
    version_agent,
)
from cora.infrastructure.idempotency import with_idempotency
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.observability import with_tracing

_BC = "agent"


@dataclass(frozen=True)
class AgentHandlers:
    """The Agent BC's handler bundle, each closed over Kernel."""

    define_agent: define_agent.IdempotentHandler
    version_agent: version_agent.Handler
    deprecate_agent: deprecate_agent.Handler
    suspend_agent: suspend_agent.Handler
    resume_agent: resume_agent.Handler
    grant_tool_to_agent: grant_tool_to_agent.Handler
    revoke_tool_from_agent: revoke_tool_from_agent.Handler
    revise_agent_budget: revise_agent_budget.Handler
    get_agent: get_agent.Handler
    re_debrief_run: re_debrief_run.IdempotentHandler | None
    promote_caution_proposal: promote_caution_proposal.IdempotentHandler


def wire_agent(deps: Kernel) -> AgentHandlers:
    """Build the Agent BC handlers from shared dependencies.

    `re_debrief_run` requires `kernel.llm` to be set (production
    `AnthropicLLMAdapter` or test `FakeLLMAdapter`). When the LLM
    is unwired (eg. dev startup without ANTHROPIC_API_KEY), the
    handler bundle carries `re_debrief_run=None`; the REST route
    + MCP tool guard on the None to return HTTP 503.
    """
    re_debrief_run_handler: re_debrief_run.IdempotentHandler | None
    if deps.llm is None:
        re_debrief_run_handler = None
    else:
        re_debrief_run_handler = with_tracing(
            with_idempotency(
                re_debrief_run.bind(deps),
                deps.idempotency_store,
                command_name="ReDebriefRun",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="ReDebriefRun",
            bc=_BC,
        )
    return AgentHandlers(
        define_agent=with_tracing(
            with_idempotency(
                define_agent.bind(deps),
                deps.idempotency_store,
                command_name="DefineAgent",
                # Handler returns UUID; cache as str (jsonb-friendly) and
                # rebuild via UUID() on retrieval.
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="DefineAgent",
            bc=_BC,
        ),
        version_agent=with_tracing(
            version_agent.bind(deps),
            command_name="VersionAgent",
            bc=_BC,
        ),
        deprecate_agent=with_tracing(
            deprecate_agent.bind(deps),
            command_name="DeprecateAgent",
            bc=_BC,
        ),
        suspend_agent=with_tracing(
            suspend_agent.bind(deps),
            command_name="SuspendAgent",
            bc=_BC,
        ),
        resume_agent=with_tracing(
            resume_agent.bind(deps),
            command_name="ResumeAgent",
            bc=_BC,
        ),
        grant_tool_to_agent=with_tracing(
            grant_tool_to_agent.bind(deps),
            command_name="GrantToolToAgent",
            bc=_BC,
        ),
        revoke_tool_from_agent=with_tracing(
            revoke_tool_from_agent.bind(deps),
            command_name="RevokeToolFromAgent",
            bc=_BC,
        ),
        revise_agent_budget=with_tracing(
            revise_agent_budget.bind(deps),
            command_name="ReviseAgentBudget",
            bc=_BC,
        ),
        get_agent=with_tracing(
            get_agent.bind(deps),
            command_name="GetAgent",
            bc=_BC,
        ),
        re_debrief_run=re_debrief_run_handler,
        promote_caution_proposal=with_tracing(
            with_idempotency(
                promote_caution_proposal.bind(deps),
                deps.idempotency_store,
                command_name="PromoteCautionProposal",
                # Handler returns UUID; cache as str (jsonb-friendly).
                serialize_result=str,
                deserialize_result=UUID,
                lock_stale_seconds=deps.settings.idempotency_lock_stale_seconds,
            ),
            command_name="PromoteCautionProposal",
            bc=_BC,
        ),
    )
