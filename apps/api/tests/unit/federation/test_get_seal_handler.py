"""Application-handler tests for `get_seal` query slice.

Singleton-per-facility lookup: the query carries the human-readable
`facility_code` (str), not a UUID. The handler derives the deterministic
stream UUID via `seal_stream_id(facility_code)` before calling
`load_seal`; `load_seal_timestamps` is keyed on `facility_code` directly
(the projection PK is TEXT). Pins authz Deny, the not-found path, and
the Path C view-bundle composition (Seal + timestamps=None when deps
lack a pool).
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.errors import UnauthorizedError
from cora.federation.features import get_seal
from cora.federation.features.get_seal import GetSeal
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.shared.facility_code import FacilityCode
from tests.unit._helpers import build_deps as _build_deps_shared
from tests.unit.federation._helpers import seed_live_seal

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_FACILITY_CODE = "aps-2bm"
_STREAM_ID = seal_stream_id(_FACILITY_CODE)
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000fe5001")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fe5099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000fe50aa")


@pytest.mark.unit
async def test_handler_returns_seal_view_on_hit() -> None:
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_NOW,
        facility_code=_FACILITY_CODE,
    )
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = get_seal.bind(deps)
    view = await handler(
        GetSeal(facility_code=_FACILITY_CODE),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is not None
    assert view.seal.facility_code == FacilityCode(_FACILITY_CODE)
    assert view.seal.current_sequence_number == 0
    assert view.seal.current_head_hash is None
    assert view.seal.initialized_by == _PRINCIPAL_ID
    # No pool in this in-memory test, so projection-sourced timestamps
    # are absent. Pin the contract: the handler returns SealView with
    # timestamps=None rather than failing.
    assert view.timestamps is None


@pytest.mark.unit
async def test_handler_returns_none_on_miss() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = get_seal.bind(deps)
    view = await handler(
        GetSeal(facility_code="no-such-facility"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is None


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await seed_live_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_NOW,
        facility_code=_FACILITY_CODE,
    )
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store, deny=True)
    handler = get_seal.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            GetSeal(facility_code=_FACILITY_CODE),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_keys_on_facility_code_not_stream_id() -> None:
    """Two facilities yield distinct stream ids via UUID5; the handler
    folds the right stream for the requested facility_code."""
    store = InMemoryEventStore()
    other_facility = "max-iv-balder"
    await seed_live_seal(
        store,
        stream_id=_STREAM_ID,
        genesis_event_id=_GENESIS_EVENT_ID,
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_NOW,
        facility_code=_FACILITY_CODE,
    )
    await seed_live_seal(
        store,
        stream_id=seal_stream_id(other_facility),
        genesis_event_id=UUID("01900000-0000-7000-8000-000000fe5002"),
        correlation_id=_CORRELATION_ID,
        principal_id=_PRINCIPAL_ID,
        initialized_at=_NOW,
        facility_code=other_facility,
    )
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = get_seal.bind(deps)

    primary = await handler(
        GetSeal(facility_code=_FACILITY_CODE),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    secondary = await handler(
        GetSeal(facility_code=other_facility),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert primary is not None
    assert secondary is not None
    assert primary.seal.facility_code == FacilityCode(_FACILITY_CODE)
    assert secondary.seal.facility_code == FacilityCode(other_facility)
