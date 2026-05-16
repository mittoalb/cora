"""Contract tests for `POST /campaigns`."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.campaign.aggregates.campaign import (
    CAMPAIGN_DESCRIPTION_MAX_LENGTH,
    CAMPAIGN_NAME_MAX_LENGTH,
    CampaignAlreadyExistsError,
)
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features.register_campaign.route import (
    _get_handler as _get_register_campaign_handler,  # pyright: ignore[reportPrivateUsage]
)


def _body(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "In-situ heating series #42",
        "intent": "Series",
        "lead_actor_id": str(uuid4()),
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_post_campaigns_returns_201_with_campaign_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/campaigns", json=_body())
    assert response.status_code == 201, response.text
    body = response.json()
    assert "campaign_id" in body
    UUID(body["campaign_id"])


@pytest.mark.contract
@pytest.mark.parametrize(
    "intent",
    ["Series", "Sweep", "Coordinated", "Block"],
)
def test_post_campaigns_accepts_each_intent(intent: str) -> None:
    with TestClient(create_app()) as client:
        response = client.post("/campaigns", json=_body(intent=intent))
    assert response.status_code == 201


@pytest.mark.contract
def test_post_campaigns_accepts_full_optional_payload() -> None:
    refs = [
        {"scheme": "proposal", "id": "2025-100"},
        {"scheme": "visit", "id": "V-77"},
    ]
    with TestClient(create_app()) as client:
        response = client.post(
            "/campaigns",
            json=_body(
                subject_id=str(uuid4()),
                description="full description",
                tags=["alpha", "beta"],
                external_refs=refs,
                external_id="DOI:10.1234/abc",
            ),
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_campaigns_rejects_unknown_intent_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/campaigns", json=_body(intent="Unknown"))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_campaigns_rejects_missing_required_fields_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/campaigns",
            json={"intent": "Series"},  # name + lead_actor_id missing
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_campaigns_rejects_missing_lead_actor_id_with_422() -> None:
    """Pins lead_actor_id REQUIRED at the wire (LIMS Study Director
    precedent; per design memo Locks §lead_actor_id REQUIRED at register).
    """
    with TestClient(create_app()) as client:
        response = client.post(
            "/campaigns",
            json={"name": "x", "intent": "Series"},  # lead_actor_id omitted
        )
    assert response.status_code == 422
    body = response.json()
    # Pydantic's missing-field detail mentions lead_actor_id.
    assert "lead_actor_id" in str(body).lower()


@pytest.mark.contract
def test_post_campaigns_rejects_external_ref_with_empty_scheme_with_400() -> None:
    """Per ExternalRef VO: scheme is bounded-text 1-50 chars after trim.

    Pydantic's `min_length=1` on the DTO catches the empty case at
    422 BEFORE the domain VO ever runs. We assert 422 (the wire-level
    boundary) and that the response body mentions the `scheme` field.
    """
    with TestClient(create_app()) as client:
        response = client.post(
            "/campaigns",
            json=_body(external_refs=[{"scheme": "", "id": "abc"}]),
        )
    # Pydantic catches the empty scheme at 422 via the DTO's min_length.
    assert response.status_code == 422
    body = response.json()
    assert "scheme" in str(body).lower()


@pytest.mark.contract
def test_post_campaigns_rejects_too_long_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/campaigns",
            json=_body(name="a" * (CAMPAIGN_NAME_MAX_LENGTH + 1)),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_campaigns_rejects_too_long_description_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/campaigns",
            json=_body(description="a" * (CAMPAIGN_DESCRIPTION_MAX_LENGTH + 1)),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_campaigns_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace passes Pydantic min_length but trips the domain VO."""
    with TestClient(create_app()) as client:
        response = client.post("/campaigns", json=_body(name="     "))
    assert response.status_code == 400
    assert "Campaign name" in response.json()["detail"]


@pytest.mark.contract
def test_post_campaigns_rejects_whitespace_only_tag_with_400() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/campaigns", json=_body(tags=["valid", "   "]))
    assert response.status_code == 400
    assert "Campaign tag" in response.json()["detail"]


@pytest.mark.contract
def test_post_campaigns_rejects_whitespace_only_external_id_with_400() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/campaigns", json=_body(external_id="     "))
    assert response.status_code == 400
    assert "Campaign external_id" in response.json()["detail"]


@pytest.mark.contract
async def test_post_campaigns_returns_409_when_handler_raises_already_exists() -> None:
    app = create_app()
    existing_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise CampaignAlreadyExistsError(existing_id)

    app.dependency_overrides[_get_register_campaign_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/campaigns", json=_body())
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_campaigns_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_register_campaign_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/campaigns", json=_body())
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
