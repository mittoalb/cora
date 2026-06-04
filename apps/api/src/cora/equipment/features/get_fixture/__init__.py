"""Vertical slice for the `GetFixture` query."""

from cora.equipment.features.get_fixture import tool
from cora.equipment.features.get_fixture.handler import Handler, bind
from cora.equipment.features.get_fixture.query import GetFixture
from cora.equipment.features.get_fixture.route import router

__all__ = [
    "GetFixture",
    "Handler",
    "bind",
    "router",
    "tool",
]
