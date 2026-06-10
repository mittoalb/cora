"""Application-handler tests for `get_clearance` query slice."""

import dataclasses
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_clearance_template_lookup import (
    InMemoryClearanceTemplateLookup,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.safety.aggregates.clearance import (
    ClearanceStatus,
    RunBinding,
    event_type_name,
    to_payload,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features import get_clearance
from cora.safety.features.get_clearance import GetClearance
from cora.safety.features.register_clearance import (
    RegisterClearance,
)
from cora.safety.features.register_clearance import (
    bind as register_clearance_bind,
)
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000011021")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000011022")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
    clearance_template_lookup: InMemoryClearanceTemplateLookup | None = None,
) -> Kernel:
    deps = _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )
    if clearance_template_lookup is not None:
        deps = dataclasses.replace(
            deps,
            clearance_template_lookup=clearance_template_lookup,
        )
    return deps


@pytest.mark.unit
async def test_get_handler_returns_state_when_clearance_exists() -> None:
    """Seed the store with a registered clearance via the register handler,
    then fetch it back via get_clearance."""
    store = InMemoryEventStore()
    template_id = clearance_template_stream_id("cora", "ESAF")
    template_lookup = InMemoryClearanceTemplateLookup()
    template_lookup.register(
        template_id=template_id,
        facility_code="cora",
        code="ESAF",
        status="Active",
        version=1,
    )
    deps = _build_deps(
        event_store=store,
        clearance_template_lookup=template_lookup,
    )
    register_handler = register_clearance_bind(deps)
    rid = uuid4()
    clearance_id = await register_handler(
        RegisterClearance(
            template_id=ClearanceTemplateId(template_id),
            facility_code="cora",
            title="Pilot",
            bindings=frozenset({RunBinding(run_id=rid)}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    get_handler = get_clearance.bind(deps)
    result = await get_handler(
        GetClearance(clearance_id=clearance_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    assert result.id == clearance_id
    assert result.template_id == ClearanceTemplateId(template_id)
    assert result.status == ClearanceStatus.DEFINED
    assert RunBinding(run_id=rid) in result.bindings


@pytest.mark.unit
async def test_get_handler_returns_none_when_clearance_not_found() -> None:
    deps = _build_deps()
    handler = get_clearance.bind(deps)
    result = await handler(
        GetClearance(clearance_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_get_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)
    handler = get_clearance.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetClearance(clearance_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_get_handler_does_not_load_when_denied() -> None:
    """An empty store + deny means the load_clearance never runs;
    the handler raises before reaching the read repo."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    handler = get_clearance.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            GetClearance(clearance_id=_NEW_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Hand-crafted-stream variant: skip register handler entirely ----------


@pytest.mark.unit
async def test_get_handler_loads_state_from_directly_seeded_event_stream() -> None:
    """Seed the store directly with a ClearanceRegistered event (no handler);
    fetching back should reconstruct identical state. Pins the load+evolve path."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    cid = uuid4()
    rid = uuid4()
    from cora.safety.aggregates.clearance import ClearanceRegistered

    template_id = clearance_template_stream_id("cora", "SAF")
    event = ClearanceRegistered(
        clearance_id=cid,
        template_id=template_id,
        template_code="SAF",
        facility_code="cora",
        title="Hand-crafted",
        bindings=({"kind": "Run", "id": str(rid)},),
        declarations=(),
        risk_band=None,
        external_id=None,
        valid_from=None,
        valid_until=None,
        parent_id=None,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=uuid4(),
        command_name="RegisterClearance",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="Clearance",
        stream_id=cid,
        expected_version=0,
        events=[new_event],
    )

    handler = get_clearance.bind(deps)
    result = await handler(
        GetClearance(clearance_id=cid),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is not None
    assert result.id == cid
    assert result.template_id == ClearanceTemplateId(template_id)
