"""The `list_practices` query slice. Cursor-paginated; backed by
`proj_recipe_practice_summary`."""

from cora.recipe.features.list_practices.handler import (
    Handler,
    PracticeListPage,
    PracticeSummaryItem,
    bind,
)
from cora.recipe.features.list_practices.query import ListPractices
from cora.recipe.features.list_practices.route import router

__all__ = [
    "Handler",
    "ListPractices",
    "PracticeListPage",
    "PracticeSummaryItem",
    "bind",
    "router",
]
