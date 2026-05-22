"""Agent's update-handler factory (thin wrapper).

Hoisted at the rule-of-three trigger: the Agent BC started with 2
transition slices (`version_agent` + `deprecate_agent`); growth to
7 (+ `suspend_agent` + `resume_agent` + `grant_tool_to_agent` +
`revoke_tool_from_agent` + `revise_agent_budget`) put it well past
the n=3 threshold that triggered the same hoist for Recipe's
Method / Plan / Practice + Subject + Asset + Supply + Procedure +
Caution + Clearance + Run + Campaign.

Per-aggregate scoping (not BC-wide) mirrors the Equipment / Recipe
precedent: Agent BC owns ONE aggregate today (Agent), but the
naming + module shape lines up with the cross-BC factory so a
future second aggregate slots in cleanly.

## Agent-side knobs closed over

  - `stream_type = "Agent"`.
  - `target_id_attr = "agent_id"` — every Agent transition command
    exposes `agent_id: UUID`.
  - `unauthorized_error = UnauthorizedError` from the Agent BC.
  - The four codec functions imported from
    `cora.agent.aggregates.agent`.

`extra_log_fields` is a per-slice optional extractor for command-
specific fields the structured log should emit (eg.
`suspend_agent` logs `reason` length so operators searching the
log can find paused agents without dumping the reason text).
"""

from collections.abc import Callable, Sequence
from typing import Any

from cora.agent.aggregates.agent import (
    AgentEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.agent.errors import UnauthorizedError
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.update_handler import make_update_handler


def make_agent_update_handler(
    deps: Kernel,
    *,
    command_name: str,
    log_prefix: str,
    decide_fn: Callable[..., Sequence[AgentEvent]],
    extra_log_fields: Callable[[Any], dict[str, Any]] | None = None,
):
    """Build an update-style handler for one Agent slice."""
    return make_update_handler(
        deps,
        stream_type="Agent",
        target_id_attr="agent_id",
        from_stored=from_stored,
        to_payload=to_payload,
        event_type_name=event_type_name,
        fold=fold,
        unauthorized_error=UnauthorizedError,
        command_name=command_name,
        log_prefix=log_prefix,
        decide_fn=decide_fn,
        extra_log_fields=extra_log_fields,
    )


__all__ = ["make_agent_update_handler"]
