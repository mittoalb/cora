"""Application handler for the `RegisterActor` command.

Glues the pure decider (`cora.access.domain.register_actor`) to the
infrastructure ports (Authorize, Clock, IdGenerator, EventStore). A
factory builds the handler as a closure over `SharedDeps`; the wire
module bundles it alongside future Access handlers; the FastAPI lifespan
attaches the bundle to `app.state.access`.

Handler shape (cross-BC pattern for *create-style* commands):

    1. authorize(actor_id, command_name, conduit) -> Allow | Deny
    2. id_generator.new_id() -> new aggregate id
    3. clock.now() -> domain timestamp
    4. decider(state=None, command, *, now, new_id) -> domain events
    5. wrap each domain event as a NewEvent (payload serialized)
    6. event_store.append(stream_type, new_id, expected_version=0, ...)

Update-style commands (later) load + fold + decide instead of skipping
to step 4. The shape splits intentionally: a freshly generated id
provably has no prior events, so the load is wasteful.
"""

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from cora.access.domain.commands import RegisterActor
from cora.access.domain.events import ActorRegistered
from cora.access.domain.register_actor import register_actor
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.ports import Deny, NewEvent

_STREAM_TYPE = "Actor"
_COMMAND_NAME = "RegisterActor"
_CONDUIT_DEFAULT = "default"


class UnauthorizedError(Exception):
    """The Authorize port denied the command."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


RegisterActorHandler = Callable[..., Awaitable[UUID]]


def make_register_actor_handler(deps: SharedDeps) -> RegisterActorHandler:
    """Build a `register_actor` handler closed over the shared deps."""

    async def handler(
        command: RegisterActor,
        *,
        actor_id: UUID,
        correlation_id: UUID,
    ) -> UUID:
        decision = await deps.authorize(
            actor_id=actor_id,
            command_name=_COMMAND_NAME,
            conduit=_CONDUIT_DEFAULT,
        )
        if isinstance(decision, Deny):
            raise UnauthorizedError(decision.reason)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        domain_events = register_actor(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
        )

        new_events = [
            _to_new_event(event, correlation_id=correlation_id) for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=new_id,
            expected_version=0,
            events=new_events,
        )
        return new_id

    return handler


def _to_new_event(
    event: ActorRegistered,
    *,
    correlation_id: UUID,
) -> NewEvent:
    """Wrap a domain event in the persistence envelope."""
    return NewEvent(
        event_type=type(event).__name__,
        schema_version=1,
        payload=_serialize_actor_registered(event),
        occurred_at=event.occurred_at,
        correlation_id=correlation_id,
        causation_id=None,
        metadata={"command": _COMMAND_NAME},
    )


def _serialize_actor_registered(event: ActorRegistered) -> dict[str, Any]:
    """Convert ActorRegistered to a JSON-friendly dict for jsonb storage.

    UUIDs and datetimes aren't natively JSON-serializable, so the
    asyncpg JSON codec needs primitives. Per-event serializers will
    multiply with the event count; we'll generalize when ≥3 events
    in this BC need it.
    """
    return {
        "actor_id": str(event.actor_id),
        "name": event.name,
        "occurred_at": event.occurred_at.isoformat(),
    }
