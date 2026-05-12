"""Unit tests for the `list_actors` handler.

Pool-less behavior + cursor encode/decode round-trips. Postgres-side
SQL is exercised in the contract + integration tests.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.access.features.list_actors import ListActors, bind
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    Deny,
    FixedIdGenerator,
    FrozenClock,
)
from cora.infrastructure.projection import InvalidCursorError, encode_cursor

_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


class _DenyAllAuthorize:
    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
    ) -> Deny:
        _ = (principal_id, command_name, conduit_id)
        return Deny(reason="denied for test")


def _build_kernel(*, deny: bool = False, with_pool: bool = False) -> Kernel:
    """Build a Kernel for handler tests. Pool-less unless `with_pool`
    is explicitly requested (Postgres-backed tests live in the
    integration suite)."""
    return Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([]),
        authorize=_DenyAllAuthorize() if deny else AllowAllAuthorize(),
        event_store=InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
        pool=None,  # explicit: in-memory test
    )


@pytest.mark.unit
async def test_handler_returns_empty_page_when_no_pool() -> None:
    """In-memory test environment has no projection table; handler
    returns an empty page so contract tests using `app_env=test`
    don't need Postgres just to hit the endpoint."""
    handler = bind(_build_kernel())

    page = await handler(
        ListActors(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    handler = bind(_build_kernel(deny=True))

    with pytest.raises(Exception, match="denied for test"):
        await handler(
            ListActors(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_cursor_for_garbage() -> None:
    """Malformed cursor propagates `InvalidCursorError` from the
    framework's decode_cursor; route layer maps to 422."""
    handler = bind(_build_kernel())

    with pytest.raises(InvalidCursorError):
        await handler(
            ListActors(cursor="not-a-real-cursor"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_accepts_well_formed_cursor() -> None:
    """A valid cursor decodes cleanly and the handler proceeds (gets
    an empty page because there's no pool, but no decode error)."""
    cursor = encode_cursor(
        created_at=_NOW,
        item_id=UUID("01900000-0000-7000-8000-000000000001"),
    )
    handler = bind(_build_kernel())

    page = await handler(
        ListActors(cursor=cursor),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert page.items == []
    assert page.next_cursor is None
