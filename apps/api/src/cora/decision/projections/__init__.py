"""Decision BC projections.

- DecisionSummaryProjection (8e): backs GET /decisions.
- DecisionRatingsProjection: backs operator-rating queries;
  latest-per-actor wins.
"""

from cora.decision.projections.ratings import DecisionRatingsProjection
from cora.decision.projections.summary import DecisionSummaryProjection

__all__ = ["DecisionRatingsProjection", "DecisionSummaryProjection"]
