"""Recipe BC projections.

Multi-aggregate BC: each of Method / Practice / Plan / Capability
gets its own projection module under this package, mirroring
Equipment's layout (asset.py + family.py). Add a new projection by
creating a new module here + re-exporting its class + adding it to
`register_recipe_projections`.
"""

from cora.recipe.projections.capability import CapabilitySummaryProjection
from cora.recipe.projections.method import MethodSummaryProjection
from cora.recipe.projections.plan import PlanSummaryProjection
from cora.recipe.projections.practice import PracticeSummaryProjection

__all__ = [
    "CapabilitySummaryProjection",
    "MethodSummaryProjection",
    "PlanSummaryProjection",
    "PracticeSummaryProjection",
]
