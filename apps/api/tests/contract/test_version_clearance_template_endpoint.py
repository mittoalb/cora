"""Contract tests for `POST /clearance-templates/{template_id}/versions`.

Pins the additive-within-Active 204 no-body transition contract for the
version-bump slice. Covers the Pydantic boundary checks (missing body
fields, `new_version` below the `ge=2` floor, malformed UUIDs in path
or body), the UnauthorizedError -> 403 mapping, the
ClearanceTemplateNotFoundError -> 404 mapping (either the target
template or the supersedes parent missing), the
ClearanceTemplateCannotVersionError -> 409 mapping (target not Active
or `new_version` not monotonic), and the
ClearanceTemplateFacilityMismatchError -> 409 mapping (parent template
belongs to a different facility). Handler swaps go through the
lifespan-built `app.state.safety` aggregate via `dataclasses.replace`,
mirroring the sibling activate slice.
"""

from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateCannotVersionError,
    ClearanceTemplateFacilityMismatchError,
    ClearanceTemplateNotFoundError,
)
from cora.safety.errors import UnauthorizedError
from cora.shared.facility_code import FacilityCode


def _body(
    *,
    new_version: int = 2,
    supersedes_template_id: str | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "new_version": new_version,
        "supersedes_template_id": supersedes_template_id or str(uuid4()),
    }
    return body


@pytest.mark.contract
def test_post_version_clearance_template_returns_204_with_no_body() -> None:
    async def _stub_handler(*_args: object, **_kwargs: object) -> None:
        return None

    template_id = uuid4()
    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            version_clearance_template=_stub_handler,
        )
        response = client.post(
            f"/clearance-templates/{template_id}/versions",
            json=_body(),
        )
    assert response.status_code == 204, response.text
    assert response.content == b""


@pytest.mark.contract
def test_post_version_clearance_template_rejects_missing_body_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/clearance-templates/{uuid4()}/versions", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_clearance_template_rejects_missing_new_version_with_422() -> None:
    body = _body()
    del body["new_version"]
    with TestClient(create_app()) as client:
        response = client.post(
            f"/clearance-templates/{uuid4()}/versions",
            json=body,
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_clearance_template_rejects_missing_supersedes_template_id_with_422() -> None:
    body = _body()
    del body["supersedes_template_id"]
    with TestClient(create_app()) as client:
        response = client.post(
            f"/clearance-templates/{uuid4()}/versions",
            json=body,
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_clearance_template_rejects_new_version_below_two_with_422() -> None:
    """The `ge=2` Pydantic floor catches the no-op bump-to-one at the boundary."""
    with TestClient(create_app()) as client:
        response = client.post(
            f"/clearance-templates/{uuid4()}/versions",
            json=_body(new_version=1),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_clearance_template_rejects_malformed_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/clearance-templates/not-a-uuid/versions",
            json=_body(),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_clearance_template_rejects_malformed_supersedes_id_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/clearance-templates/{uuid4()}/versions",
            json={"new_version": 2, "supersedes_template_id": "not-a-uuid"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_version_clearance_template_returns_403_when_authorize_denies() -> None:
    async def _denying_handler(*_args: object, **_kwargs: object) -> None:
        raise UnauthorizedError("denied for test")

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            version_clearance_template=_denying_handler,
        )
        response = client.post(
            f"/clearance-templates/{uuid4()}/versions",
            json=_body(),
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_version_clearance_template_returns_404_when_template_unknown() -> None:
    template_id = uuid4()

    async def _missing_handler(*_args: object, **_kwargs: object) -> None:
        raise ClearanceTemplateNotFoundError(template_id)

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            version_clearance_template=_missing_handler,
        )
        response = client.post(
            f"/clearance-templates/{template_id}/versions",
            json=_body(),
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_version_clearance_template_returns_404_when_parent_template_unknown() -> None:
    """A missing supersedes parent surfaces via the same NotFound -> 404 mapping."""
    parent_id = uuid4()

    async def _missing_parent_handler(*_args: object, **_kwargs: object) -> None:
        raise ClearanceTemplateNotFoundError(parent_id)

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            version_clearance_template=_missing_parent_handler,
        )
        response = client.post(
            f"/clearance-templates/{uuid4()}/versions",
            json=_body(supersedes_template_id=str(parent_id)),
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_version_clearance_template_returns_409_when_not_in_active() -> None:
    template_id = uuid4()

    async def _conflict_handler(*_args: object, **_kwargs: object) -> None:
        from cora.safety.aggregates.clearance_template import ClearanceTemplateStatus

        raise ClearanceTemplateCannotVersionError(template_id, ClearanceTemplateStatus.DRAFT)

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            version_clearance_template=_conflict_handler,
        )
        response = client.post(
            f"/clearance-templates/{template_id}/versions",
            json=_body(),
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_version_clearance_template_returns_409_on_facility_mismatch() -> None:
    template_id = uuid4()

    async def _mismatch_handler(*_args: object, **_kwargs: object) -> None:
        raise ClearanceTemplateFacilityMismatchError(
            template_id,
            FacilityCode("cora"),
            FacilityCode("other"),
        )

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            version_clearance_template=_mismatch_handler,
        )
        response = client.post(
            f"/clearance-templates/{template_id}/versions",
            json=_body(),
        )
    assert response.status_code == 409


@pytest.mark.contract
def test_post_version_clearance_template_path_and_body_round_trip() -> None:
    """The template_id from the path and the body fields thread through
    unchanged to the wired handler's command argument."""
    template_id = uuid4()
    parent_id = uuid4()
    captured: dict[str, object] = {}

    async def _capturing_handler(command: object, **_kwargs: object) -> None:
        captured["template_id"] = command.template_id  # type: ignore[attr-defined]
        captured["new_version"] = command.new_version  # type: ignore[attr-defined]
        captured["supersedes_template_id"] = command.supersedes_template_id  # type: ignore[attr-defined]

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            version_clearance_template=_capturing_handler,
        )
        response = client.post(
            f"/clearance-templates/{template_id}/versions",
            json=_body(new_version=3, supersedes_template_id=str(parent_id)),
        )
    assert response.status_code == 204, response.text
    assert captured["template_id"] == template_id
    assert captured["new_version"] == 3
    assert captured["supersedes_template_id"] == parent_id
