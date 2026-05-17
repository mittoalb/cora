"""Agent BC subscribers (Phase 8f-b iter 2b, 8f-c iter 3).

Agent subscribers are the FIRST side-effecting consumers in CORA's
projection-worker framework: they observe domain events and emit
new events back into the event store. All prior subscribers were
projections (read-side writers only).

Current registry: `RunDebriefSubscriber` (8f-b iter 2b) +
`CautionDrafterSubscriber` (8f-c iter 3). Both fire on terminal
Run events; namespaces are kept distinct to avoid Decision-id
collision (see `test_subscriber_namespace_distinct_from_run_debrief`).

The architecture pin
`tests/architecture/test_agent_subscribers_completeness.py`
asserts every subscriber file in this package is registered in
`cora.agent._subscribers.register_agent_subscribers`.
"""

from cora.agent.subscribers.caution_drafter import CautionDrafterSubscriber
from cora.agent.subscribers.run_debrief import RunDebriefSubscriber

__all__ = ["CautionDrafterSubscriber", "RunDebriefSubscriber"]
