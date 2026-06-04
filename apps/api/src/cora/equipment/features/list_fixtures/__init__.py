"""Vertical slice for the `ListFixtures` query."""

from cora.equipment.features.list_fixtures import tool
from cora.equipment.features.list_fixtures.handler import (
    FixtureListPage,
    FixtureSummaryItem,
    Handler,
    bind,
)
from cora.equipment.features.list_fixtures.query import ListFixtures
from cora.equipment.features.list_fixtures.route import router

__all__ = [
    "FixtureListPage",
    "FixtureSummaryItem",
    "Handler",
    "ListFixtures",
    "bind",
    "router",
    "tool",
]
