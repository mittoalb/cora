"""Port `Protocol`s — contracts the application layer depends on.

Adapters implementing these ports live alongside (in `infrastructure/`) and are
wired into `SharedDeps` at startup. Domain and application code imports only
from `ports/`, never from adapter modules.
"""

from cora.infrastructure.ports.authorize import (
    Allow,
    AllowAllAuthorize,
    Authorize,
    AuthzResult,
    Deny,
)
from cora.infrastructure.ports.clock import Clock, FrozenClock, SystemClock
from cora.infrastructure.ports.event_publisher import EventPublisher
from cora.infrastructure.ports.event_store import (
    ConcurrencyError,
    EventStore,
    NewEvent,
    StoredEvent,
)
from cora.infrastructure.ports.id_generator import IdGenerator, UUIDv7Generator

__all__ = [
    "Allow",
    "AllowAllAuthorize",
    "Authorize",
    "AuthzResult",
    "Clock",
    "ConcurrencyError",
    "Deny",
    "EventPublisher",
    "EventStore",
    "FrozenClock",
    "IdGenerator",
    "NewEvent",
    "StoredEvent",
    "SystemClock",
    "UUIDv7Generator",
]
