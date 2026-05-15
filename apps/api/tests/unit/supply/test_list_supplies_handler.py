"""Application-handler tests for `list_supplies` query slice.

Without a Postgres pool the handler short-circuits to an empty page;
real query behavior is in the integration suite.
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.supply.errors import UnauthorizedError
from cora.supply.features import list_supplies
from cora.supply.features.list_supplies import ListSupplies
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.unit
async def test_handler_returns_empty_page_when_pool_is_none() -> None:
    """In-memory test deps have no Postgres pool; handler returns empty."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_supplies.bind(deps)
    page = await handler(
        ListSupplies(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.unit
async def test_handler_passes_through_filters() -> None:
    """Filter args reach the handler; SQL is exercised in integration tests."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_supplies.bind(deps)
    page = await handler(
        ListSupplies(
            scope="Beamline",
            kind="LiquidNitrogen",
            status="Available",
            limit=20,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Pool is None so still returns empty; the test verifies the handler accepts the filter shape.
    assert page.items == []


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps_shared(ids=[], now=_NOW, deny=True)
    handler = list_supplies.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ListSupplies(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
