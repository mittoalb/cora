"""Application-handler tests for `list_procedures` query slice.

Without a Postgres pool the handler short-circuits to an empty page;
real query behavior is in the integration suite.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.operation.errors import UnauthorizedError
from cora.operation.features import list_procedures
from cora.operation.features.list_procedures import ListProcedures

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")

# Module-level import of the shared in-memory deps builder; deferred
# inline because tests/unit/_helpers is also imported by other modules.
from tests.unit._helpers import build_deps as _build_deps_shared  # noqa: E402


@pytest.mark.unit
async def test_handler_returns_empty_page_when_pool_is_none() -> None:
    """In-memory test deps have no Postgres pool; handler returns empty."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_procedures.bind(deps)
    page = await handler(
        ListProcedures(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.unit
async def test_handler_passes_through_status_filter() -> None:
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_procedures.bind(deps)
    page = await handler(
        ListProcedures(status="Running", limit=20),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []


@pytest.mark.unit
async def test_handler_passes_through_all_filters() -> None:
    """Filter args reach the handler; SQL is exercised in integration tests."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_procedures.bind(deps)
    page = await handler(
        ListProcedures(
            status="Completed",
            kind="bakeout",
            parent_run_id=uuid4(),
            target_asset_id=uuid4(),
            limit=10,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps_shared(ids=[], now=_NOW, deny=True)
    handler = list_procedures.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ListProcedures(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
