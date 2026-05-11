"""Vertical slice for the `DefinePractice` command.

Module-as-namespace surface, symmetric with the other create-style
command slices:

    from cora.recipe.features import define_practice

    cmd = define_practice.DefinePractice(name="...", method_id=..., site_id=...)
    handler = define_practice.bind(deps)
    practice_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.recipe.features.define_practice import tool
from cora.recipe.features.define_practice.command import DefinePractice
from cora.recipe.features.define_practice.decider import decide
from cora.recipe.features.define_practice.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.recipe.features.define_practice.route import router

__all__ = [
    "DefinePractice",
    "Handler",
    "IdempotentHandler",
    "bind",
    "decide",
    "router",
    "tool",
]
