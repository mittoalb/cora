"""Application-handler tests for `list_cautions` query slice.

Without a Postgres pool the handler short-circuits to an empty page;
real query behavior is in the integration suite. These tests pin:

  - empty-page no-pool branch
  - authorize Deny -> UnauthorizedError
  - cursor decode roundtrip + bind position
  - filter pass-through (incl. status-default-to-'Active' + 'all'
    sentinel + min_severity ordinal mapping)
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from cora.caution.errors import UnauthorizedError
from cora.caution.features import list_cautions
from cora.caution.features.list_cautions import ListCautions
from cora.caution.features.list_cautions.handler import (
    _LIST_NO_CURSOR_SQL,  # pyright: ignore[reportPrivateUsage]
    _LIST_WITH_CURSOR_SQL,  # pyright: ignore[reportPrivateUsage]
    _resolve_min_severity_ordinal,  # pyright: ignore[reportPrivateUsage]
    _resolve_status_filter,  # pyright: ignore[reportPrivateUsage]
)
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import Allow
from cora.infrastructure.projection import encode_cursor
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAUTION_ID = UUID("01900000-0000-7000-8000-00000000c001")
_TARGET_ID = UUID("01900000-0000-7000-8000-00000000c002")
_AUTHOR_ID = UUID("01900000-0000-7000-8000-00000000c003")


@pytest.mark.unit
async def test_handler_returns_empty_page_when_pool_is_none() -> None:
    """In-memory test deps have no Postgres pool; handler returns empty."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_cautions.bind(deps)
    page = await handler(
        ListCautions(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.unit
async def test_handler_passes_through_filters() -> None:
    """Filter args reach the handler; SQL is exercised in integration tests."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    handler = list_cautions.bind(deps)
    page = await handler(
        ListCautions(
            target_kind="Asset",
            target_id=_TARGET_ID,
            category="Wear",
            severity="Caution",
            min_severity="Caution",
            status="all",
            tag="hexapod",
            author_actor_id=_AUTHOR_ID,
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
    handler = list_cautions.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            ListCautions(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ----- _resolve_status_filter -----------------------------------------------


@pytest.mark.unit
def test_resolve_status_filter_defaults_none_to_active() -> None:
    """The design memo's default: omitted status -> hide Superseded + Retired."""
    assert _resolve_status_filter(None) == "Active"


@pytest.mark.unit
def test_resolve_status_filter_sentinel_all_disables_filter() -> None:
    """`status='all'` is the operator opt-in to see everything."""
    assert _resolve_status_filter("all") is None


@pytest.mark.unit
@pytest.mark.parametrize("status", ["Active", "Superseded", "Retired"])
def test_resolve_status_filter_passes_real_values_through(status: str) -> None:
    assert _resolve_status_filter(status) == status


# ----- _resolve_min_severity_ordinal ----------------------------------------


@pytest.mark.unit
def test_resolve_min_severity_ordinal_none_returns_none() -> None:
    assert _resolve_min_severity_ordinal(None) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "expected"),
    [("Notice", 0), ("Caution", 1), ("Warning", 2)],
)
def test_resolve_min_severity_ordinal_maps_each_severity(name: str, expected: int) -> None:
    """Notice<Caution<Warning ordinal ladder; >= comparison via the SQL CASE."""
    assert _resolve_min_severity_ordinal(name) == expected


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
        "caution_id": _CAUTION_ID,
        "target_kind": "Asset",
        "target_id": _TARGET_ID,
        "category": "Wear",
        "severity": "Caution",
        "text": "hexapod stalls below 0.5 mm/s",
        "workaround": "run at 0.6 mm/s",
        "author_actor_id": _AUTHOR_ID,
        "tags": ["hexapod"],
        "expires_at": None,
        "propagate_to_children": False,
        "status": "Active",
        "parent_caution_id": None,
        "superseded_by_caution_id": None,
        "retired_reason": None,
        "registered_at": _NOW,
        "last_status_changed_at": None,
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
    """The handler binds limit, target_kind, target_id, category, severity,
    min_severity_ord, effective_status, tag, author_actor_id in that order
    for the no-cursor SQL variant."""
    deps, conn = _deps_with_pool([])
    handler = list_cautions.bind(deps)
    await handler(
        ListCautions(
            target_kind="Asset",
            target_id=_TARGET_ID,
            category="Wear",
            severity="Caution",
            min_severity="Warning",
            status="Active",
            tag="hexapod",
            author_actor_id=_AUTHOR_ID,
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
    assert args[1] == "Asset"
    assert args[2] == _TARGET_ID
    assert args[3] == "Wear"
    assert args[4] == "Caution"
    assert args[5] == 2  # Warning -> ordinal 2
    assert args[6] == "Active"
    assert args[7] == "hexapod"
    assert args[8] == _AUTHOR_ID


@pytest.mark.unit
async def test_handler_status_default_active_when_query_status_is_none() -> None:
    """No status passed -> handler binds 'Active' to the effective_status slot."""
    deps, conn = _deps_with_pool([])
    handler = list_cautions.bind(deps)
    await handler(
        ListCautions(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _sql, *args = conn.fetch_args[0]
    assert args[6] == "Active"


@pytest.mark.unit
async def test_handler_status_all_disables_filter() -> None:
    """`status='all'` -> handler binds None to the effective_status slot."""
    deps, conn = _deps_with_pool([])
    handler = list_cautions.bind(deps)
    await handler(
        ListCautions(status="all"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _sql, *args = conn.fetch_args[0]
    assert args[6] is None


@pytest.mark.unit
async def test_handler_with_cursor_uses_with_cursor_sql_variant() -> None:
    """Passing a cursor switches to the WITH_CURSOR SQL + binds (cursor_at, cursor_id)."""
    deps, conn = _deps_with_pool([])
    handler = list_cautions.bind(deps)
    cursor = encode_cursor(created_at=_NOW, item_id=_CAUTION_ID)
    await handler(
        ListCautions(cursor=cursor),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    sql, *args = conn.fetch_args[0]
    assert sql == _LIST_WITH_CURSOR_SQL
    # cursor_at lives at $10 -> args[9]; cursor_id at $11 -> args[10]
    assert args[9] == _NOW
    assert args[10] == _CAUTION_ID


@pytest.mark.unit
async def test_handler_returns_items_and_next_cursor_when_overflow() -> None:
    """When the projection returns limit+1 rows, the handler emits a next_cursor
    from the last kept item's (registered_at, caution_id)."""
    # Build 2 rows with distinct ids; limit=1 so 1 kept + 1 overflow.
    id_a = UUID("01900000-0000-7000-8000-00000000aaaa")
    id_b = UUID("01900000-0000-7000-8000-00000000bbbb")
    rows = [_row(caution_id=id_a), _row(caution_id=id_b)]
    deps, _conn = _deps_with_pool(rows)
    handler = list_cautions.bind(deps)
    page = await handler(
        ListCautions(limit=1),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].caution_id == id_a
    assert page.next_cursor is not None


@pytest.mark.unit
async def test_handler_no_next_cursor_when_rows_within_limit() -> None:
    deps, _conn = _deps_with_pool([_row()])
    handler = list_cautions.bind(deps)
    page = await handler(
        ListCautions(limit=5),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.next_cursor is None


@pytest.mark.unit
async def test_handler_row_mapping_round_trips_every_column() -> None:
    expires = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    parent_id = UUID("01900000-0000-7000-8000-0000000000dd")
    superseded_by = UUID("01900000-0000-7000-8000-0000000000ee")
    row = _row(
        target_kind="Procedure",
        category="ProcedureGotcha",
        severity="Warning",
        tags=["alpha", "beta"],
        expires_at=expires,
        propagate_to_children=True,
        status="Superseded",
        parent_caution_id=parent_id,
        superseded_by_caution_id=superseded_by,
        retired_reason=None,
        last_status_changed_at=_NOW,
    )
    deps, _conn = _deps_with_pool([row])
    handler = list_cautions.bind(deps)
    page = await handler(
        ListCautions(status="all"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    item = page.items[0]
    assert item.target_kind == "Procedure"
    assert item.category == "ProcedureGotcha"
    assert item.severity == "Warning"
    assert item.tags == ["alpha", "beta"]
    assert item.expires_at == expires
    assert item.propagate_to_children is True
    assert item.status == "Superseded"
    assert item.parent_caution_id == parent_id
    assert item.superseded_by_caution_id == superseded_by
    assert item.retired_reason is None
    assert item.last_status_changed_at == _NOW


@pytest.mark.unit
async def test_handler_cursor_decode_roundtrip() -> None:
    """Encoded (NOW, CAUTION_ID) cursor decodes back to the same pair before
    binding into the WITH_CURSOR variant. Pins the helper round-trip end to end."""
    cursor = encode_cursor(created_at=_NOW, item_id=_CAUTION_ID)
    deps, conn = _deps_with_pool([])
    handler = list_cautions.bind(deps)
    await handler(
        ListCautions(cursor=cursor),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    _sql, *args = conn.fetch_args[0]
    assert args[9] == _NOW
    assert args[10] == _CAUTION_ID


@pytest.mark.unit
async def test_handler_authorize_called_with_query_name_constant() -> None:
    """Pins the BOLA gating key: command_name == 'ListCautions'."""
    deps = _build_deps_shared(ids=[], now=_NOW)
    authorize_mock = AsyncMock(return_value=Allow())
    object.__setattr__(deps, "authorize", authorize_mock)
    handler = list_cautions.bind(deps)
    await handler(
        ListCautions(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    authorize_mock.assert_awaited_once()
    call = authorize_mock.await_args
    assert call is not None
    assert call.kwargs["command_name"] == "ListCautions"
