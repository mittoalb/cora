"""Application handler for the `register_actor` slice.

Glues the pure decider in this slice to the infrastructure ports
(Authorize, Clock, IdGenerator, EventStore). `bind(deps)` returns a
handler closure; the BC's wire module bundles it; the FastAPI lifespan
attaches the bundle to `app.state.access`.

Module-as-namespace pattern: callers import this slice as
`from cora.access.features import register_actor` and use
`register_actor.bind(deps)` returning a `register_actor.Handler`.

Handler shape (cross-BC pattern for create-style commands):

    1. authorize(principal_id, command_name, conduit) -> Allow | Deny
    2. id_generator.new_id() -> new aggregate id
    3. clock.now() -> domain timestamp
    4. decide(state=None, command, *, now, new_id) -> domain events
    5. wrap each domain event as a NewEvent (payload serialized)
    6. event_store.append(stream_type, new_id, expected_version=0, ...)

Update-style commands (later) load + fold + decide instead of skipping
to step 4. The shape splits intentionally: a freshly generated id
provably has no prior events, so the load is wasteful.
"""

from typing import Protocol
from uuid import UUID

from cora.access.aggregates.actor import to_new_event
from cora.access.errors import UnauthorizedError
from cora.access.features.register_actor.command import RegisterActor
from cora.access.features.register_actor.decider import decide
from cora.infrastructure.deps import SharedDeps
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny

_STREAM_TYPE = "Actor"
_COMMAND_NAME = "RegisterActor"
_CONDUIT_DEFAULT = "default"

# structlog loggers are lazy: get_logger() returns a proxy and config is
# applied at first .info() call. Module-level binding is safe even though
# configure_logging() runs later in build_shared_deps().
_log = get_logger(__name__)


class Handler(Protocol):
    """Bare register_actor handler — what `bind()` returns.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator (in `cora.access._idempotency`) wraps a bare Handler
    into an `IdempotentHandler`; production wiring in `wire.py` always
    wraps. Tests can use bare Handler directly when they don't need
    idempotency semantics.
    """

    async def __call__(
        self,
        command: RegisterActor,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """register_actor handler with Idempotency-Key support.

    Same shape as `Handler` plus an optional `idempotency_key` kwarg
    (default None means: behave like the bare handler). The wrapped
    form lives on `app.state.access.register_actor` in production;
    routes pass through the inbound `Idempotency-Key` header.
    """

    async def __call__(
        self,
        command: RegisterActor,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: SharedDeps) -> Handler:
    """Build a register_actor handler closed over the shared deps."""

    async def handler(
        command: RegisterActor,
        *,
        principal_id: UUID,
        correlation_id: UUID,
    ) -> UUID:
        _log.info(
            "register_actor.start",
            command_name=_COMMAND_NAME,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit=_CONDUIT_DEFAULT,
        )
        if isinstance(decision, Deny):
            _log.info(
                "register_actor.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
        )

        new_events = [
            to_new_event(
                event,
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=new_id,
            expected_version=0,
            events=new_events,
        )

        _log.info(
            "register_actor.success",
            command_name=_COMMAND_NAME,
            actor_id=str(new_id),
            correlation_id=str(correlation_id),
            event_count=len(new_events),
        )
        return new_id

    return handler
