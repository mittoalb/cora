"""Application-handler tests for `define_clearance_template` slice.

Covers:
  - happy path: returns stream_id derived from (facility_code, code) and
    appends a single ClearanceTemplateDefined event with the envelope
    (event_id, correlation_id, principal_id, occurred_at) wired by the
    handler from clock + id-generator + caller-supplied ids
  - authz Deny -> UnauthorizedError; no event appended
  - facility lookup miss -> ClearanceTemplateFacilityNotFoundError;
    no event appended
  - stream_id is deterministic for the same (facility_code, code) pair
  - expected_version=0 (genesis-only)
  - defined_by on the event payload equals the principal_id (ActorId
    wraps UUID transparently on serialization)
"""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.adapters.in_memory_facility_lookup import InMemoryFacilityLookup
from cora.infrastructure.kernel import Kernel
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateFacilityNotFoundError,
    clearance_template_stream_id,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features import define_clearance_template
from cora.safety.features.define_clearance_template import DefineClearanceTemplate
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c1f01")
_SECOND_EVENT_ID = UUID("01900000-0000-7000-8000-0000000c1f02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000c1f03")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000c1f04")

_FACILITY_CODE = "cora"
_TEMPLATE_CODE = "esaf.standard"
_TEMPLATE_TITLE = "Experiment Safety Assessment Form"


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
    facility_lookup: InMemoryFacilityLookup | None = None,
) -> Kernel:
    return _build_deps_shared(
        ids=[_EVENT_ID, _SECOND_EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
        facility_lookup=facility_lookup,
    )


def _command(
    *,
    code: str = _TEMPLATE_CODE,
    title: str = _TEMPLATE_TITLE,
    facility_code: str = _FACILITY_CODE,
) -> DefineClearanceTemplate:
    return DefineClearanceTemplate(
        code=code,
        title=title,
        facility_code=facility_code,
    )


@pytest.mark.unit
async def test_handler_returns_stream_id_derived_from_facility_and_code() -> None:
    deps = _build_deps()
    handler = define_clearance_template.bind(deps)

    result = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    expected = clearance_template_stream_id(_FACILITY_CODE, _TEMPLATE_CODE)
    assert result == expected


@pytest.mark.unit
async def test_handler_appends_single_defined_event_with_envelope() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_clearance_template.bind(deps)

    template_id = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("ClearanceTemplate", template_id)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "ClearanceTemplateDefined"
    assert stored.event_id == _EVENT_ID
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.occurred_at == _NOW
    assert stored.payload["template_id"] == str(template_id)
    assert stored.payload["facility_code"] == _FACILITY_CODE
    assert stored.payload["code"] == _TEMPLATE_CODE
    assert stored.payload["title"] == _TEMPLATE_TITLE
    assert stored.payload["version"] == 1


@pytest.mark.unit
async def test_handler_threads_principal_id_onto_defined_by() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_clearance_template.bind(deps)

    template_id = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("ClearanceTemplate", template_id)
    assert UUID(events[0].payload["defined_by"]) == _PRINCIPAL_ID


@pytest.mark.unit
async def test_handler_appends_at_expected_version_zero() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    handler = define_clearance_template.bind(deps)

    template_id = await handler(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # A second invocation on the same (facility_code, code) pair derives
    # the same stream_id and must collide on expected_version=0, proving
    # the handler appended as genesis rather than tacking onto an
    # arbitrary version.
    _ = template_id
    with pytest.raises(Exception):  # noqa: B017 -- store-specific concurrency error class
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_derives_deterministic_stream_id_across_calls() -> None:
    deps_one = _build_deps()
    deps_two = _build_deps()

    first = await define_clearance_template.bind(deps_one)(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    second = await define_clearance_template.bind(deps_two)(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert first == second
    assert first == clearance_template_stream_id(_FACILITY_CODE, _TEMPLATE_CODE)


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = define_clearance_template.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_append_when_denied() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = define_clearance_template.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            _command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    stream_id = clearance_template_stream_id(_FACILITY_CODE, _TEMPLATE_CODE)
    events, version = await store.load("ClearanceTemplate", stream_id)
    assert version == 0
    assert events == []


@pytest.mark.unit
async def test_handler_raises_facility_not_found_for_unknown_code() -> None:
    store = InMemoryEventStore()
    # Empty facility lookup: no seeded code resolves; lookup_by_code -> None.
    empty_lookup = InMemoryFacilityLookup()
    deps = _build_deps(event_store=store, facility_lookup=empty_lookup)
    handler = define_clearance_template.bind(deps)

    with pytest.raises(ClearanceTemplateFacilityNotFoundError):
        await handler(
            _command(facility_code="ghost"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    stream_id = clearance_template_stream_id("ghost", _TEMPLATE_CODE)
    events, version = await store.load("ClearanceTemplate", stream_id)
    assert version == 0
    assert events == []
