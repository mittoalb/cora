"""Vertical slice: `re_debrief_run`.

Operator-triggered on-demand RunDebriefer. Pattern C from the design
memo: re-invoke the RunDebriefer agent against a specific Run and
get a fresh `DecisionRegistered` back.

Use cases:
  - First Debrief was rated `misleading`; operator wants a fresh take.
  - Original auto-fired Debrief landed `DebriefDeferred` (LLM
    exhausted); the API is healthy now; operator retries.
  - A new model version or read-scope expansion landed; operator
    re-evaluates a historical Run.

Distinct from the subscriber's event-driven Pattern A (8f-b iter 2b):

| axis                | Pattern A subscriber          | Pattern C on-demand        |
|---------------------|-------------------------------|----------------------------|
| trigger             | terminal Run event            | operator MCP / REST call   |
| principal_id        | agent self                    | operator (HTTP header)     |
| actor_id            | RunDebriefer Agent            | RunDebriefer Agent (same)  |
| decision_id         | uuid5 from terminal event_id  | uuidv7 from id_generator   |
| at-most-once via    | deterministic id + retry no-op| Idempotency-Key (Brandur)  |
| parent_id           | None (genesis Decision)       | operator-supplied (chain)  |
| DebriefDeferred     | yes, on LLM exhaust           | yes, on LLM exhaust        |

Idempotency-Key wrapping: `with_idempotency` at wire.py mirrors the
create-style pattern from `define_agent` / `register_decision` /
etc. An operator retry with the same key replays the cached
decision_id.
"""

from cora.agent.features.re_debrief_run.command import ReDebriefRun
from cora.agent.features.re_debrief_run.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.agent.features.re_debrief_run.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "ReDebriefRun",
    "bind",
    "router",
]
