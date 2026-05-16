"""Contract tests for `POST /cautions`."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.caution.aggregates.caution import (
    CAUTION_TEXT_MAX_LENGTH,
    CAUTION_WORKAROUND_MAX_LENGTH,
    CautionAlreadyExistsError,
)
from cora.caution.errors import UnauthorizedError
from cora.caution.features.register_caution.route import (
    _get_handler as _get_register_caution_handler,  # pyright: ignore[reportPrivateUsage]
)


def _body(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "target": {"kind": "Asset", "id": str(uuid4())},
        "category": "Wear",
        "severity": "Caution",
        "text": "hexapod stalls below 0.5 mm/s",
        "workaround": "run at 0.6 mm/s",
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_post_cautions_returns_201_with_caution_id_for_asset_target() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/cautions", json=_body())
    assert response.status_code == 201, response.text
    body = response.json()
    assert "caution_id" in body
    UUID(body["caution_id"])


@pytest.mark.contract
def test_post_cautions_derives_author_actor_id_from_request_principal() -> None:
    """Author identity is derived from the request envelope's principal_id
    by the handler (no spoofing path at the API surface)."""
    from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

    with TestClient(create_app()) as client:
        register = client.post("/cautions", json=_body())
        assert register.status_code == 201, register.text
        cid = register.json()["caution_id"]
        get_response = client.get(f"/cautions/{cid}")
    assert get_response.status_code == 200
    assert get_response.json()["author_actor_id"] == str(SYSTEM_PRINCIPAL_ID)


@pytest.mark.contract
def test_post_cautions_accepts_procedure_target() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/cautions",
            json=_body(target={"kind": "Procedure", "id": str(uuid4())}),
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
@pytest.mark.parametrize("severity", ["Notice", "Caution", "Warning"])
def test_post_cautions_accepts_each_severity(severity: str) -> None:
    with TestClient(create_app()) as client:
        response = client.post("/cautions", json=_body(severity=severity))
    assert response.status_code == 201


@pytest.mark.contract
@pytest.mark.parametrize(
    "category",
    [
        "Wear",
        "Calibration",
        "Wiring",
        "OperationalWindow",
        "InterlockQuirk",
        "ProcedureGotcha",
    ],
)
def test_post_cautions_accepts_each_category(category: str) -> None:
    with TestClient(create_app()) as client:
        response = client.post("/cautions", json=_body(category=category))
    assert response.status_code == 201


@pytest.mark.contract
def test_post_cautions_rejects_danger_severity_with_422() -> None:
    """Anti-hook #4: no Danger tier."""
    with TestClient(create_app()) as client:
        response = client.post("/cautions", json=_body(severity="Danger"))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_cautions_rejects_run_target_kind_with_422() -> None:
    """RunTarget deferred day-1."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/cautions",
            json=_body(target={"kind": "Run", "id": str(uuid4())}),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_cautions_rejects_missing_required_fields_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/cautions",
            json={
                "target": {"kind": "Asset", "id": str(uuid4())},
                "category": "Wear",
                "severity": "Caution",
                # text + workaround missing
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_cautions_rejects_too_long_text_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/cautions",
            json=_body(text="a" * (CAUTION_TEXT_MAX_LENGTH + 1)),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_cautions_rejects_too_long_workaround_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/cautions",
            json=_body(workaround="a" * (CAUTION_WORKAROUND_MAX_LENGTH + 1)),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_cautions_rejects_whitespace_only_text_with_400() -> None:
    """Whitespace passes Pydantic min_length but trips the domain VO."""
    with TestClient(create_app()) as client:
        response = client.post("/cautions", json=_body(text="     "))
    assert response.status_code == 400
    assert "Caution text" in response.json()["detail"]


@pytest.mark.contract
def test_post_cautions_rejects_whitespace_only_workaround_with_400() -> None:
    """Anti-hook #1: workaround REQUIRED, also non-blank after trim."""
    with TestClient(create_app()) as client:
        response = client.post("/cautions", json=_body(workaround="    "))
    assert response.status_code == 400
    assert "Caution workaround" in response.json()["detail"]


@pytest.mark.contract
def test_post_cautions_rejects_whitespace_only_tag_with_400() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/cautions", json=_body(tags=["valid-tag", "   "]))
    assert response.status_code == 400
    assert "Caution tag" in response.json()["detail"]


@pytest.mark.contract
def test_post_cautions_rejects_past_expires_at_with_400() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/cautions",
            json=_body(expires_at="2020-01-01T00:00:00+00:00"),
        )
    assert response.status_code == 400


@pytest.mark.contract
async def test_post_cautions_returns_409_when_handler_raises_already_exists() -> None:
    app = create_app()
    existing_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise CautionAlreadyExistsError(existing_id)

    app.dependency_overrides[_get_register_caution_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/cautions", json=_body())
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_cautions_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_register_caution_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/cautions", json=_body())
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
