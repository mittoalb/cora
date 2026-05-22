"""Agent BC subscriber registration for the projection worker.

ROLE: This module is the REGISTRATION HELPER
(`register_agent_subscribers(registry, deps)`), NOT the home for
the subscribers themselves. Subscribers live in
`cora.agent.subscribers/` (the sub-package); this leading-underscore
module is the bridge between that package and the projection
worker's `ProjectionRegistry`.

The split mirrors the per-BC `register_<bc>_projections` convention
(`cora.<bc>._projections` registers what lives in `cora.<bc>.projections/`).
Agent BC has no `_projections` because it owns no projections (read-
side); it only owns SIDE-EFFECTING subscribers that emit new events.

## Conditional registration

If `kernel.llm is None` (`ANTHROPIC_API_KEY` unset), no subscribers
are registered and a warning is logged. The alternative (raising at
app startup) would refuse to boot a deployment that wants to defer
Agent rollout.

## Registered subscribers

  - `RunDebriefSubscriber` (8f-b iter 2b) — terminal Run -> one
    advisory Decision with AAR narrative + 6-value choice.
  - `CautionDrafterSubscriber` (8f-c iter 3) — terminal Run -> one
    `DecisionRegistered(context="CautionProposal")` with 5-value
    choice + optional proposed-Caution tuple. Operator-promoted
    via the `promote_caution_proposal` slice.

Both subscribers run concurrently and INDEPENDENTLY in the
projection worker. Per [[project-caution-drafter-design]] Q4 lock:
DO NOT widen the subscriber framework at iter 3. Named widening
triggers (3rd subscriber / >50ms blocking / first cross-subscriber
ordering dependency) documented in the design memo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.agent.subscribers.caution_drafter import make_caution_drafter_subscriber
from cora.agent.subscribers.run_debrief import make_run_debrief_subscriber
from cora.infrastructure.logging import get_logger

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.projection.registry import ProjectionRegistry

_log = get_logger(__name__)


def register_agent_subscribers(registry: ProjectionRegistry, deps: Kernel) -> None:
    """Register Agent BC's subscribers into the projection-worker registry."""
    if deps.llm is None:
        _log.warning(
            "agent_subscriber.skipped",
            subscribers=["run_debrief", "caution_drafter"],
            reason="kernel.llm is None (ANTHROPIC_API_KEY not configured)",
        )
        return

    run_debrief = make_run_debrief_subscriber(deps)
    registry.register(run_debrief)
    _log.info(
        "agent_subscriber.registered",
        subscriber=run_debrief.name,
        subscribed_event_types=sorted(run_debrief.subscribed_event_types),
    )

    caution_drafter = make_caution_drafter_subscriber(deps)
    registry.register(caution_drafter)
    _log.info(
        "agent_subscriber.registered",
        subscriber=caution_drafter.name,
        subscribed_event_types=sorted(caution_drafter.subscribed_event_types),
    )


__all__ = ["register_agent_subscribers"]
