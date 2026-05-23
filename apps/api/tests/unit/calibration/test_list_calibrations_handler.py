"""Application-handler tests for `list_calibrations` query slice.

Without a Postgres pool the handler short-circuits to an empty page;
real query behavior is in the integration suite. These tests pin:

  - empty-page no-pool branch
  - authorize Deny -> UnauthorizedError
  - filter pass-through (canonical list-typed
    `latest_revision_statuses` / `latest_revision_source_kinds`)
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.calibration.errors import UnauthorizedError
from cora.calibration.features import list_calibrations
from cora.calibration.features.list_calibrations import ListCalibrations
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_SUBSYSTEM_ID = UUID("01900000-0000-7000-8000-000000ca4001")


@pytest.mark.unit
async def test_handler_returns_empty_page_when_pool_is_none() -> None:
    """In-memory test deps have no Postgres pool; handler returns empty."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_calibrations.bind(deps)
    page = await handler(
        ListCalibrations(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.unit
async def test_handler_accepts_canonical_filter_shape() -> None:
    """`ListCalibrations` carries canonical list-typed
    latest_revision_statuses + latest_revision_source_kinds; the
    route/MCP-tool layer translates user-facing UX before calling here."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_calibrations.bind(deps)
    page = await handler(
        ListCalibrations(
            target_id=_SUBSYSTEM_ID,
            quantity="rotation_center",
            latest_revision_statuses=["Provisional", "Verified"],
            latest_revision_source_kinds=["measured", "computed"],
            limit=20,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Pool is None: returns empty. The test pins the handler accepts the filter shape.
    assert page.items == []


@pytest.mark.unit
async def test_handler_default_query_uses_no_filters() -> None:
    """`ListCalibrations()` (no args) means "no filter" on every
    dimension. Unlike Caution, calibration has no default-to-Active
    convention — operators commonly want to see all calibrations
    (provisional + verified across all source kinds) so the
    no-default discipline lives at the dataclass + route + MCP tool
    levels uniformly."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_calibrations.bind(deps)
    query = ListCalibrations()
    assert query.target_id is None
    assert query.quantity is None
    assert query.latest_revision_statuses is None
    assert query.latest_revision_source_kinds is None
    page = await handler(
        query,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps_shared(ids=[], now=_NOW, deny=True)
    handler = list_calibrations.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ListCalibrations(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
