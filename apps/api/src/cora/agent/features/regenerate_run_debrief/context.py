"""Cross-aggregate context for the `regenerate_run_debrief` slice's pure decider.

Per `docs/reference/patterns.md` Cross-aggregate validation: the handler
pre-loads anything the decider needs from other aggregates (Actor here)
and the LLM extracts the per-call choice/confidence/reasoning before
calling the pure decider. The decider takes this context as an opaque
keyword-only parameter; no I/O, no awaits.

The split keeps the genesis decider signature canonical
``decide(state, command, *, context, now, new_id)`` even though the
command itself stays minimal (just `run_id` + `parent_decision_id`,
the operator-supplied bits).
"""

from dataclasses import dataclass
from typing import Any

from cora.access.aggregates.actor import Actor


@dataclass(frozen=True)
class RegenerateRunDebriefContext:
    """Handler-pre-loaded context for the on-demand RunDebriefer slice.

    Carries:

      - `actor`: the agent Actor whose identity authors the Decision
        (handler raises AgentNotSeededError / AgentDeactivatedError before
        constructing this context).
      - `choice` / `confidence` / `reasoning`: the LLM-extracted bits of
        the response, or the DebriefDeferred fallback when the LLM call
        failed.
      - `extra_inputs`: optional extension to the base
        `inputs` dict (used by the DebriefDeferred path to record
        `failure_error_class`). Merged after the base keys; collisions
        on `run_id` / `trigger` / `prompt_template_id` are silently
        overwritten by the caller's overrides.
    """

    actor: Actor
    choice: str
    confidence: float | None
    reasoning: str
    extra_inputs: dict[str, Any] | None = None
