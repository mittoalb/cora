"""Agent BC subscribers.

Agent subscribers are the FIRST side-effecting consumers in CORA's
projection-worker framework: they observe domain events and emit
new events back into the event store. All prior subscribers were
projections (read-side writers only).

Current registry: `RunDebrieferSubscriber` + `CautionDrafterSubscriber`.
Both fire on terminal Run events; namespaces are kept distinct to
avoid Decision-id collision (see
`test_subscriber_namespace_distinct_from_run_debriefer`).

The architecture pin
`tests/architecture/test_agent_subscribers_completeness.py`
asserts every subscriber file in this package is registered in
`cora.agent._subscribers.register_agent_subscribers`.
"""

from cora.agent.subscribers.caution_drafter import CautionDrafterSubscriber
from cora.agent.subscribers.run_debriefer import RunDebrieferSubscriber

__all__ = ["CautionDrafterSubscriber", "RunDebrieferSubscriber"]
