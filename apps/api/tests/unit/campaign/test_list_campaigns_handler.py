"""Application-handler tests for `list_campaigns` query slice.

Without a Postgres pool the handler short-circuits to an empty page;
real query behavior is in the integration suite. These tests pin:

  - empty-page no-pool branch
  - authorize Deny -> UnauthorizedError
  - cursor decode roundtrip + bind position
  - filter pass-through (incl. status default-to-OPEN-set + 'all'
    sentinel + exact status binding)
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from cora.campaign.errors import UnauthorizedError
from cora.campaign.features import list_campaigns
from cora.campaign.features.list_campaigns import ListCampaigns
from cora.campaign.features.list_campaigns.handler import (
    _LIST_NO_CURSOR_SQL,  # pyright: ignore[reportPrivateUsage]
    _LIST_WITH_CURSOR_SQL,  # pyright: ignore[reportPrivateUsage]
    _OPEN_STATUSES,  # pyright: ignore[reportPrivateUsage]
    _resolve_status_filter,  # pyright: ignore[reportPrivateUsage]
)
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import Allow
from cora.infrastructure.projection import encode_cursor
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAMPAIGN_ID = UUID("01900000-0000-7000-8000-00000000d001")
_LEAD_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000d002")
_SUBJECT_ID = UUID("01900000-0000-7000-8000-00000000d003")


@pytest.mark.unit
async def test_handler_returns_empty_page_when_pool_is_none() -> None:
    """In-memory test deps have no Postgres pool; handler returns empty."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_campaigns.bind(deps)
    page = await handler(
        ListCampaigns(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.unit
async def test_handler_passes_through_filters() -> None:
    """Filter args reach the handler; SQL is exercised in integration tests."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_campaigns.bind(deps)
    page = await handler(
        ListCampaigns(
            status="all",
            intent="Operando",
            lead_actor_id=_LEAD_ACTOR_ID,
            subject_id=_SUBJECT_ID,
            tag="hexapod",
            limit=20,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Pool is None, returns empty; the test verifies the handler accepts the filter shape.
    assert page.items == []


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps_shared(ids=[], now=_NOW, deny=True)
    handler = list_campaigns.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ListCampaigns(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ----- _resolve_status_filter -----------------------------------------------


@pytest.mark.unit
def test_resolve_status_filter_defaults_none_to_open_set() -> None:
    """The design memo's default: omitted status -> OPEN set (Planned+Active+Held)."""
    assert _resolve_status_filter(None) == _OPEN_STATUSES
    assert _resolve_status_filter(None) == ("Planned", "Active", "Held")


@pytest.mark.unit
def test_resolve_status_filter_sentinel_all_disables_filter() -> None:
    """`status='all'` is the operator opt-in to see every status."""
    assert _resolve_status_filter("all") is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    ["Planned", "Active", "Held", "Closed", "Abandoned"],
)
def test_resolve_status_filter_passes_real_values_through_as_single_tuple(status: str) -> None:
    """An exact status value collapses to a 1-tuple for the ANY(...) bind."""
    assert _resolve_status_filter(status) == (status,)


# ----- Bind-position assertions via mocked pool -----------------------------


class _FakeConn:
    """Records fetch calls so we can assert the argument vector + SQL variant."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.fetch_args: list[tuple[Any, ...]] = []

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        # Record the SQL itself in the args tuple so tests can pin the variant.
        self.fetch_args.append((sql, *args))
        return self._rows


class _FakeAcquireCM:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *_: Any) -> None:
        return None


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def acquire(self) -> _FakeAcquireCM:
        return _FakeAcquireCM(self._conn)


def _row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "campaign_id": _CAMPAIGN_ID,
        "name": "operando battery",
        "intent": "Operando",
        "status": "Active",
        "lead_actor_id": _LEAD_ACTOR_ID,
        "subject_id": _SUBJECT_ID,
        "description": None,
        "tags": ["hexapod"],
        "external_id": None,
        "run_count": 0,
        "registered_at": _NOW,
        "started_at": _NOW,
        "last_status_changed_at": _NOW,
        "last_status_reason": None,
    }
    base.update(overrides)
    return base


def _deps_with_pool(rows: list[dict[str, Any]]) -> tuple[Kernel, _FakeConn]:
    deps = _build_deps_shared(ids=[], now=_NOW)
    fake_conn = _FakeConn(rows)
    # Replace the deps.pool attribute with our fake; the handler only touches
    # `deps.pool.acquire()`.
    object.__setattr__(deps, "pool", _FakePool(fake_conn))
    return deps, fake_conn


@pytest.mark.unit
async def test_handler_filter_binds_map_one_to_one_with_sql_positions() -> None:
    """The handler binds limit, status_array, intent, lead_actor_id, subject_id, tag
    in that order for the no-cursor SQL variant."""
    deps, conn = _deps_with_pool([])
    handler = list_campaigns.bind(deps)
    await handler(
        ListCampaigns(
            status="Active",
            intent="Operando",
            lead_actor_id=_LEAD_ACTOR_ID,
            subject_id=_SUBJECT_ID,
            tag="hexapod",
            limit=5,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(conn.fetch_args) == 1
    sql, *args = conn.fetch_args[0]
    assert sql == _LIST_NO_CURSOR_SQL
    # limit + 1 keyset overfetch
    assert args[0] == 6
    assert args[1] == ["Active"]  # status_array
    assert args[2] == "Operando"
    assert args[3] == _LEAD_ACTOR_ID
    assert args[4] == _SUBJECT_ID
    assert args[5] == "hexapod"


@pytest.mark.unit
async def test_handler_status_default_open_set_when_query_status_is_none() -> None:
    """No status passed -> handler binds the OPEN set (Planned+Active+Held)."""
    deps, conn = _deps_with_pool([])
    handler = list_campaigns.bind(deps)
    await handler(
        ListCampaigns(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _sql, *args = conn.fetch_args[0]
    assert args[1] == ["Planned", "Active", "Held"]


@pytest.mark.unit
async def test_handler_status_all_disables_filter() -> None:
    """`status='all'` -> handler binds None to the status_array slot."""
    deps, conn = _deps_with_pool([])
    handler = list_campaigns.bind(deps)
    await handler(
        ListCampaigns(status="all"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _sql, *args = conn.fetch_args[0]
    assert args[1] is None


@pytest.mark.unit
async def test_handler_status_closed_filters_to_single_value() -> None:
    """`status='Closed'` -> handler binds ['Closed']."""
    deps, conn = _deps_with_pool([])
    handler = list_campaigns.bind(deps)
    await handler(
        ListCampaigns(status="Closed"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _sql, *args = conn.fetch_args[0]
    assert args[1] == ["Closed"]


@pytest.mark.unit
async def test_handler_with_cursor_uses_with_cursor_sql_variant() -> None:
    """Passing a cursor switches to the WITH_CURSOR SQL + binds (cursor_at, cursor_id)."""
    deps, conn = _deps_with_pool([])
    handler = list_campaigns.bind(deps)
    cursor = encode_cursor(created_at=_NOW, item_id=_CAMPAIGN_ID)
    await handler(
        ListCampaigns(cursor=cursor),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    sql, *args = conn.fetch_args[0]
    assert sql == _LIST_WITH_CURSOR_SQL
    # cursor_at lives at $7 -> args[6]; cursor_id at $8 -> args[7]
    assert args[6] == _NOW
    assert args[7] == _CAMPAIGN_ID


@pytest.mark.unit
async def test_handler_returns_items_and_next_cursor_when_overflow() -> None:
    """When the projection returns limit+1 rows, the handler emits a next_cursor
    from the last kept item's (registered_at, campaign_id)."""
    id_a = UUID("01900000-0000-7000-8000-00000000aaaa")
    id_b = UUID("01900000-0000-7000-8000-00000000bbbb")
    rows = [_row(campaign_id=id_a), _row(campaign_id=id_b)]
    deps, _conn = _deps_with_pool(rows)
    handler = list_campaigns.bind(deps)
    page = await handler(
        ListCampaigns(limit=1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].campaign_id == id_a
    assert page.next_cursor is not None


@pytest.mark.unit
async def test_handler_no_next_cursor_when_rows_within_limit() -> None:
    deps, _conn = _deps_with_pool([_row()])
    handler = list_campaigns.bind(deps)
    page = await handler(
        ListCampaigns(limit=5),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.next_cursor is None


@pytest.mark.unit
async def test_handler_row_mapping_round_trips_every_column() -> None:
    started = datetime(2026, 5, 17, 13, 0, 0, tzinfo=UTC)
    last_changed = datetime(2026, 5, 17, 15, 0, 0, tzinfo=UTC)
    row = _row(
        name="parameter sweep, T_K",
        intent="ParameterSweep",
        status="Held",
        description="three-axis sweep",
        tags=["alpha", "beta"],
        external_id="DOI:10.example/proj-002",
        run_count=12,
        started_at=started,
        last_status_changed_at=last_changed,
        last_status_reason="beam dump",
    )
    deps, _conn = _deps_with_pool([row])
    handler = list_campaigns.bind(deps)
    page = await handler(
        ListCampaigns(status="all"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    item = page.items[0]
    assert item.name == "parameter sweep, T_K"
    assert item.intent == "ParameterSweep"
    assert item.status == "Held"
    assert item.description == "three-axis sweep"
    assert item.tags == ["alpha", "beta"]
    assert item.external_id == "DOI:10.example/proj-002"
    assert item.run_count == 12
    assert item.started_at == started
    assert item.last_status_changed_at == last_changed
    assert item.last_status_reason == "beam dump"


@pytest.mark.unit
async def test_handler_cursor_decode_roundtrip() -> None:
    """Encoded (NOW, CAMPAIGN_ID) cursor decodes back to the same pair before
    binding into the WITH_CURSOR variant."""
    cursor = encode_cursor(created_at=_NOW, item_id=_CAMPAIGN_ID)
    deps, conn = _deps_with_pool([])
    handler = list_campaigns.bind(deps)
    await handler(
        ListCampaigns(cursor=cursor),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _sql, *args = conn.fetch_args[0]
    assert args[6] == _NOW
    assert args[7] == _CAMPAIGN_ID


@pytest.mark.unit
async def test_handler_authorize_called_with_query_name_constant() -> None:
    """Pins the BOLA gating key: command_name == 'ListCampaigns'."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    authorize_mock = AsyncMock(return_value=Allow())
    object.__setattr__(deps, "authorize", authorize_mock)
    handler = list_campaigns.bind(deps)
    await handler(
        ListCampaigns(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    authorize_mock.assert_awaited_once()
    call = authorize_mock.await_args
    assert call is not None
    assert call.kwargs["command_name"] == "ListCampaigns"
