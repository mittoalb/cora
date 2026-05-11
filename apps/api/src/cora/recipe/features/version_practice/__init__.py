"""Vertical slice for the `VersionPractice` command.

Module-as-namespace surface:

    from cora.recipe.features import version_practice

    cmd = version_practice.VersionPractice(practice_id=..., version_tag="v2")
    handler = version_practice.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.recipe.features.version_practice import tool
from cora.recipe.features.version_practice.command import VersionPractice
from cora.recipe.features.version_practice.decider import decide
from cora.recipe.features.version_practice.handler import Handler, bind
from cora.recipe.features.version_practice.route import router

__all__ = [
    "Handler",
    "VersionPractice",
    "bind",
    "decide",
    "router",
    "tool",
]
