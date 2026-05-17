"""Agent BC prompt registry (Python module).

Phase 8f-b iter 2b. Per [[project-agent-bc-research]] the
event-sourced `PromptTemplate` aggregate is deferred to
rule-of-three trigger ("second prompt revision ships"); pre-trigger
the prompts live as Python module constants keyed by
`prompt_template_id` (UUID).

Each prompt module exposes a `build_chat_request(...)` builder that
returns an `LLMChatRequest` ready for `LLMPort.chat()`. The
builders are pure (no I/O), so subscribers can construct requests
in-memory and the LLM-cache layering stays a single design choice
per agent.

Today the registry has one entry: `RUN_DEBRIEF_PROMPT_TEMPLATE_ID`
mapping to `cora.agent.prompts.run_debrief`. Future prompts
(RecipeScreener at 8f-c) follow the same pattern.
"""

from uuid import UUID

from cora.agent.prompts.run_debrief import (
    RUN_DEBRIEF_PROMPT_TEMPLATE_ID,
    RunDebriefPayload,
    build_run_debrief_chat_request,
)

# Resolve a prompt_template_id to a free-form one-liner description.
# Maps the registry slot to the implementation; future PromptTemplate
# aggregate replaces this dict with a projection.
KNOWN_PROMPT_TEMPLATES: dict[UUID, str] = {
    RUN_DEBRIEF_PROMPT_TEMPLATE_ID: "RunDebrief v1: terminal-Run AAR narrative + advisory choice",
}


__all__ = [
    "KNOWN_PROMPT_TEMPLATES",
    "RUN_DEBRIEF_PROMPT_TEMPLATE_ID",
    "RunDebriefPayload",
    "build_run_debrief_chat_request",
]
