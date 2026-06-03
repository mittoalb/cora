"""Vertical slice for the `RegisterFixture` command."""

from cora.equipment.features.register_fixture import tool
from cora.equipment.features.register_fixture.command import RegisterFixture
from cora.equipment.features.register_fixture.context import RegisterFixtureContext
from cora.equipment.features.register_fixture.decider import decide
from cora.equipment.features.register_fixture.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.equipment.features.register_fixture.route import router

__all__ = [
    "Handler",
    "IdempotentHandler",
    "RegisterFixture",
    "RegisterFixtureContext",
    "bind",
    "decide",
    "router",
    "tool",
]
