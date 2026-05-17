"""Agent BC subscribers (Phase 8f-b iter 2b).

Agent subscribers are the FIRST side-effecting consumers in CORA's
projection-worker framework: they observe domain events and emit
new events back into the event store. All prior subscribers were
projections (read-side writers only).

Today the registry has one subscriber: `RunDebriefSubscriber`,
which fires on terminal Run events and emits an advisory
`DecisionRegistered`.
"""

from cora.agent.subscribers.run_debrief import RunDebriefSubscriber

__all__ = ["RunDebriefSubscriber"]
