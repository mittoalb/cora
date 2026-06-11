"""Vertical slice for the `RegisterEdition` command."""

from cora.data.features.register_edition import tool
from cora.data.features.register_edition.command import (
    CreatorEntry,
    RegisterEdition,
)
from cora.data.features.register_edition.context import (
    EditionRegistrationContext,
)
from cora.data.features.register_edition.decider import decide
from cora.data.features.register_edition.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.data.features.register_edition.route import router

__all__ = [
    "CreatorEntry",
    "EditionRegistrationContext",
    "Handler",
    "IdempotentHandler",
    "RegisterEdition",
    "bind",
    "decide",
    "router",
    "tool",
]
