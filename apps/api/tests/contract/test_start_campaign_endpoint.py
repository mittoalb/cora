"""Contract tests for `POST /campaigns/{campaign_id}/start`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features.start_campaign.route import (
    _get_handler as _get_start_campaign_handler,  # pyright: ignore[reportPrivateUsage]
)


def _register(client: TestClient) -> str:
    response = client.post(
        "/campaigns",
        json={
            "name": "test",
            "intent": "Series",
            "lead_actor_id": str(uuid4()),
        },
    )
    assert response.status_code == 201
    return str(response.json()["campaign_id"])


@pytest.mark.contract
def test_post_start_returns_204_on_planned_campaign() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        response = client.post(f"/campaigns/{cid}/start")
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_start_returns_404_when_campaign_absent() -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/campaigns/{uuid4()}/start")
    assert response.status_code == 404


@pytest.mark.contract
def test_post_start_returns_409_on_already_started_campaign() -> None:
    with TestClient(create_app()) as client:
        cid = _register(client)
        first = client.post(f"/campaigns/{cid}/start")
        assert first.status_code == 204
        second = client.post(f"/campaigns/{cid}/start")
    assert second.status_code == 409


@pytest.mark.contract
def test_post_start_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_start_campaign_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(f"/campaigns/{uuid4()}/start")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
