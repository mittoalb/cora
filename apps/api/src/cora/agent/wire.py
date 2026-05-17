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

## Wired handlers (8f-a)

  - `define_agent`    (cross-BC atomic; create-style; idempotency-wrapped)
  - `version_agent`   (transition; no idempotency wrap)
  - `deprecate_agent` (transition; no idempotency wrap)
  - `get_agent`       (query)
"""

from dataclasses import dataclass
from uuid import UUID

from cora.agent.features import (
    define_agent,
    deprecate_agent,
    get_agent,
    re_debrief_run,
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
    get_agent: get_agent.Handler
    re_debrief_run: re_debrief_run.IdempotentHandler | None


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
        get_agent=with_tracing(
            get_agent.bind(deps),
            command_name="GetAgent",
            bc=_BC,
        ),
        re_debrief_run=re_debrief_run_handler,
    )
