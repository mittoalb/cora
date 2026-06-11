"""Contract tests for `GET /clearance-templates/{template_id}`.

The query slice's HTTP wire surface: 200 + ClearanceTemplateResponse on
hit, 404 on miss, 403 on Authorize-port denial, 422 on a malformed UUID
path parameter. The happy path stubs `_get_handler` via
`app.dependency_overrides` and returns a domain `ClearanceTemplate`
state object; the route DTO mapping is what is under test, not the
event-sourced load path.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplate,
    ClearanceTemplateCode,
    ClearanceTemplateStatus,
    ClearanceTemplateTitle,
    ClearanceTemplateVersion,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features.get_clearance_template.route import (
    _get_handler as _get_get_clearance_template_handler,  # pyright: ignore[reportPrivateUsage]
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId


def _template(
    *,
    template_id: UUID,
    code: str = "radiation-safety-form",
    title: str = "Radiation Safety Form",
    facility_code: str = "cora",
    status: ClearanceTemplateStatus = ClearanceTemplateStatus.DRAFT,
    version: int = 1,
    supersedes_template_id: UUID | None = None,
    external_ref: str | None = None,
) -> ClearanceTemplate:
    return ClearanceTemplate(
        id=template_id,
        facility_code=FacilityCode(facility_code),
        code=ClearanceTemplateCode(code),
        title=ClearanceTemplateTitle(title),
        defined_at=datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC),
        defined_by=ActorId(uuid4()),
        status=status,
        version=ClearanceTemplateVersion(version),
        supersedes_template_id=supersedes_template_id,
        external_ref=external_ref,
    )


@pytest.mark.contract
def test_get_clearance_template_returns_200_with_full_state() -> None:
    app = create_app()
    template_id = uuid4()
    supersedes_id = uuid4()
    template = _template(
        template_id=template_id,
        supersedes_template_id=supersedes_id,
        external_ref="LIMS-CT-42",
    )

    async def fake_handler(*args: object, **kwargs: object) -> ClearanceTemplate:
        _ = (args, kwargs)
        return template

    app.dependency_overrides[_get_get_clearance_template_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get(f"/clearance-templates/{template_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(template_id)
    assert body["code"] == "radiation-safety-form"
    assert body["title"] == "Radiation Safety Form"
    assert body["facility_code"] == "cora"
    assert body["version"] == 1
    assert body["status"] == "Draft"
    assert body["supersedes_template_id"] == str(supersedes_id)
    assert body["external_ref"] == "LIMS-CT-42"
    assert body["defined_at"] == "2026-06-09T12:00:00+00:00"
    UUID(body["defined_by"])


@pytest.mark.contract
def test_get_clearance_template_returns_200_with_nullable_fields_omitted() -> None:
    """`supersedes_template_id` and `external_ref` serialize as JSON null
    when the template has never been superseded and carries no external ref."""
    app = create_app()
    template_id = uuid4()
    template = _template(template_id=template_id)

    async def fake_handler(*args: object, **kwargs: object) -> ClearanceTemplate:
        _ = (args, kwargs)
        return template

    app.dependency_overrides[_get_get_clearance_template_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get(f"/clearance-templates/{template_id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["supersedes_template_id"] is None
    assert body["external_ref"] is None


@pytest.mark.contract
def test_get_clearance_template_returns_404_when_handler_returns_none() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_get_clearance_template_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get(f"/clearance-templates/{uuid4()}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.contract
def test_get_clearance_template_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_get_clearance_template_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get(f"/clearance-templates/{uuid4()}")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_get_clearance_template_returns_422_for_malformed_uuid_path_param() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/clearance-templates/not-a-uuid")
    assert response.status_code == 422
