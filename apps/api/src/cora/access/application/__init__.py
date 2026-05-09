"""Access application layer: command handlers, integration events, queries.

Public surface:
    - register_actor handler factory + UnauthorizedError (the application error)
    - AccessHandlers + wire_access(deps)  -- composition for the lifespan
"""

from cora.access.application.register_actor_handler import (
    RegisterActorHandler,
    UnauthorizedError,
    make_register_actor_handler,
)
from cora.access.application.wire import AccessHandlers, wire_access

__all__ = [
    "AccessHandlers",
    "RegisterActorHandler",
    "UnauthorizedError",
    "make_register_actor_handler",
    "wire_access",
]
