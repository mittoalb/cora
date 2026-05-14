"""Unit tests for the `list_actors` handler.

Pool-less behavior + cursor encode/decode round-trips. Postgres-side
SQL is exercised in the contract + integration tests.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.access.features.list_actors import ListActors, bind
from cora.infrastructure.projection import InvalidCursorError, encode_cursor
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.unit
async def test_handler_returns_empty_page_when_no_pool() -> None:
    """In-memory test environment has no projection table; handler
    returns an empty page so contract tests using `app_env=test`
    don't need Postgres just to hit the endpoint."""
    handler = bind(build_deps(now=_NOW))

    page = await handler(
        ListActors(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    handler = bind(build_deps(now=_NOW, deny=True))

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
    handler = bind(build_deps(now=_NOW))

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
    handler = bind(build_deps(now=_NOW))

    page = await handler(
        ListActors(cursor=cursor),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert page.items == []
    assert page.next_cursor is None
