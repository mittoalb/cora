"""Access BC projections.

Each projection lives in its own module; this package's __init__
re-exports them so `register_access_projections` (in the BC's
top-level wiring) can import from one place.
"""

from cora.access.projections.actor_summary import ActorSummaryProjection

__all__ = ["ActorSummaryProjection"]
