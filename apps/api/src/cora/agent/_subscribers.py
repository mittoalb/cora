"""Agent BC subscriber registration for the projection worker.

Phase 8f-b iter 2b. ROLE: This module is the REGISTRATION HELPER
(`register_agent_subscribers(registry, deps)`), NOT the home for
the subscribers themselves. Subscribers live in `cora.agent.subscribers/`
(the sub-package); this leading-underscore module is the bridge
between that package and the projection worker's `ProjectionRegistry`.

The split mirrors the per-BC `register_<bc>_projections` convention
(`cora.<bc>._projections` registers what lives in `cora.<bc>.projections/`).
Agent BC has no `_projections` because it owns no projections (read-
side); it only owns SIDE-EFFECTING subscribers that emit new events.

## Conditional registration

If `kernel.llm is None` (`ANTHROPIC_API_KEY` unset), the
subscriber is NOT registered and a warning is logged. The
alternative (raising at app startup) would refuse to boot a
deployment that wants to defer Agent rollout. Deployments that
WANT to enforce LLM-required can configure that with a startup
gate; this module's contract is "register if possible, log if
not". (Note: `make_run_debrief_subscriber` raises `RuntimeError`
on a None LLM -- that's the contract for callers who bypass this
registration helper.)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.agent.subscribers.run_debrief import make_run_debrief_subscriber
from cora.infrastructure.logging import get_logger

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.projection.registry import ProjectionRegistry

_log = get_logger(__name__)


def register_agent_subscribers(registry: ProjectionRegistry, deps: Kernel) -> None:
    """Register Agent BC's subscribers into the projection-worker registry.

    Today: one subscriber (`RunDebriefSubscriber`). Future agents at
    8f-c add their own subscribers here.
    """
    if deps.llm is None:
        _log.warning(
            "agent_subscriber.skipped",
            subscriber="run_debrief",
            reason="kernel.llm is None (ANTHROPIC_API_KEY not configured)",
        )
        return

    subscriber = make_run_debrief_subscriber(deps)
    registry.register(subscriber)
    _log.info(
        "agent_subscriber.registered",
        subscriber=subscriber.name,
        subscribed_event_types=sorted(subscriber.subscribed_event_types),
    )


__all__ = ["register_agent_subscribers"]
