"""Unit tests for the `list_subjects` handler. Pool-less (in-memory
test environment); end-to-end pagination is in the integration suite.

Uses the shared `tests/unit/_helpers.build_deps` factory (per the
post-8e-1c Option-4 audit consolidation; first BC to migrate to the
helper as part of Option 1)."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.projection import InvalidCursorError, encode_cursor
from cora.subject.features.list_subjects import ListSubjects, bind
from tests.unit._helpers import build_deps

_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)


@pytest.mark.unit
async def test_handler_returns_empty_page_when_no_pool() -> None:
    """In-memory test environment has no projection table; handler
    returns an empty page (the `app_env=test` convenience path)."""
    handler = bind(build_deps())

    page = await handler(
        ListSubjects(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    handler = bind(build_deps(deny=True))

    with pytest.raises(Exception, match="denied for test"):
        await handler(
            ListSubjects(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_invalid_cursor_for_garbage() -> None:
    handler = bind(build_deps())

    with pytest.raises(InvalidCursorError):
        await handler(
            ListSubjects(cursor="not-a-real-cursor"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_accepts_well_formed_cursor() -> None:
    cursor = encode_cursor(
        created_at=_NOW,
        item_id=UUID("01900000-0000-7000-8000-000000000001"),
    )
    handler = bind(build_deps())

    page = await handler(
        ListSubjects(cursor=cursor),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert page.items == []
    assert page.next_cursor is None
