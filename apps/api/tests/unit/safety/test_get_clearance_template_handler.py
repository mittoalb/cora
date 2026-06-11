"""Application-handler tests for `get_clearance_template` query slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateCode,
    ClearanceTemplateDefined,
    ClearanceTemplateStatus,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
    event_type_name,
    to_payload,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features import get_clearance_template
from cora.safety.features.get_clearance_template import GetClearanceTemplate
from cora.shared.facility_code import FacilityCode
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000012021")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000012022")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_FACILITY_CODE = "cora"
_TEMPLATE_CODE = "ESAF-v1"
_TEMPLATE_TITLE = "Experiment Safety Assessment Form"


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    return _build_deps_shared(
        ids=[_NEW_ID, _EVENT_ID],
        now=_NOW,
        event_store=event_store,
        deny=deny,
    )


async def _seed_defined(
    store: InMemoryEventStore,
    *,
    template_id: UUID,
    facility_code: str = _FACILITY_CODE,
    code: str = _TEMPLATE_CODE,
    title: str = _TEMPLATE_TITLE,
    version: int = 1,
    supersedes_template_id: UUID | None = None,
    external_ref: str | None = None,
) -> None:
    """Seed the in-memory event store with a single ClearanceTemplateDefined
    event so fold-on-read can reconstruct the aggregate."""
    event = ClearanceTemplateDefined(
        template_id=template_id,
        facility_code=facility_code,
        code=code,
        title=title,
        occurred_at=_NOW,
        defined_by=_PRINCIPAL_ID,
        version=version,
        supersedes_template_id=supersedes_template_id,
        external_ref=external_ref,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=uuid4(),
        command_name="DefineClearanceTemplate",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_PRINCIPAL_ID,
    )
    await store.append(
        stream_type="ClearanceTemplate",
        stream_id=template_id,
        expected_version=0,
        events=[new_event],
    )


@pytest.mark.unit
async def test_get_handler_returns_state_when_template_exists() -> None:
    """Seed a ClearanceTemplateDefined event directly, then fetch back via
    get_clearance_template. Fold-on-read reconstructs the aggregate from
    the stored event."""
    store = InMemoryEventStore()
    template_id = uuid4()
    await _seed_defined(store, template_id=template_id)
    deps = _build_deps(event_store=store)

    handler = get_clearance_template.bind(deps)
    result = await handler(
        GetClearanceTemplate(template_id=template_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result is not None
    assert result.id == template_id
    assert result.code == ClearanceTemplateCode(_TEMPLATE_CODE)
    assert result.title == ClearanceTemplateTitle(_TEMPLATE_TITLE)
    assert result.facility_code == FacilityCode(_FACILITY_CODE)
    assert result.version == ClearanceTemplateVersion(1)
    assert result.status == ClearanceTemplateStatus.DRAFT


@pytest.mark.unit
async def test_get_handler_returns_none_when_template_not_found() -> None:
    """Empty event store: fold-on-read produces None; handler returns None."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)

    handler = get_clearance_template.bind(deps)
    result = await handler(
        GetClearanceTemplate(template_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result is None


@pytest.mark.unit
async def test_get_handler_raises_unauthorized_on_deny() -> None:
    deps = _build_deps(deny=True)

    handler = get_clearance_template.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetClearanceTemplate(template_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_get_handler_does_not_load_when_denied() -> None:
    """Empty store + deny: the load_clearance_template never runs because
    the handler raises before reaching the read repo. A non-existent
    template id still surfaces UnauthorizedError, not None."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)

    handler = get_clearance_template.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            GetClearanceTemplate(template_id=_NEW_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_get_handler_passes_through_facility_code_supersedes_and_external_ref() -> None:
    """Optional event payload fields (facility_code, supersedes_template_id,
    external_ref) round-trip through fold-on-read into the loaded state."""
    store = InMemoryEventStore()
    template_id = uuid4()
    prev_template_id = uuid4()
    await _seed_defined(
        store,
        template_id=template_id,
        facility_code="aps-2bm",
        code="SAF-screening",
        title="Safety Screening Form",
        version=2,
        supersedes_template_id=prev_template_id,
        external_ref="LIMS:SAF-screening:v2",
    )
    deps = _build_deps(event_store=store)

    handler = get_clearance_template.bind(deps)
    result = await handler(
        GetClearanceTemplate(template_id=template_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert result is not None
    assert result.facility_code == FacilityCode("aps-2bm")
    assert result.code == ClearanceTemplateCode("SAF-screening")
    assert result.version == ClearanceTemplateVersion(2)
    assert result.supersedes_template_id == prev_template_id
    assert result.external_ref == "LIMS:SAF-screening:v2"
