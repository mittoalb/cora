"""Contract tests for `GET /campaigns`.

End-to-end pagination/filter behavior against a real projection lives
in the integration suite. These tests pin the contract: empty page
when no data, status-code shape, parameter validation, and the
authorize-Deny -> 403 path.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.campaign.errors import UnauthorizedError
from cora.campaign.features.list_campaigns.handler import Handler as ListCampaignsHandler
from cora.campaign.features.list_campaigns.route import (
    _get_handler as _get_list_campaigns_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_campaigns_returns_empty_page_with_no_data(client: TestClient) -> None:
    with client:
        response = client.get("/campaigns")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
@pytest.mark.parametrize(
    "status_value",
    ["Planned", "Active", "Held", "Closed", "Abandoned", "all"],
)
def test_get_campaigns_accepts_each_status_including_all_sentinel(
    client: TestClient, status_value: str
) -> None:
    """Five concrete statuses + 'all' sentinel; design memo: default is the OPEN
    set (Planned + Active + Held), 'all' to include Closed + Abandoned. The route
    translates 'all' to None (no filter) and routes the rest as a single-element
    list per the force-conform contract."""
    with client:
        response = client.get(f"/campaigns?status={status_value}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_campaigns_accepts_multi_value_status(client: TestClient) -> None:
    """`?status=Planned&status=Active` narrows to those two statuses; distinct
    from the `?status=all` sentinel that disables the filter."""
    with client:
        response = client.get("/campaigns?status=Planned&status=Active")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_campaigns_rejects_status_all_mixed_with_explicit_with_422(
    client: TestClient,
) -> None:
    """`?status=all&status=Active` is ambiguous (disable filter OR narrow?);
    the route 422s rather than guessing."""
    with client:
        response = client.get("/campaigns?status=all&status=Active")
    assert response.status_code == 422


@pytest.mark.contract
@pytest.mark.parametrize(
    "intent_value",
    ["Series", "Sweep", "Coordinated", "Block"],
)
def test_get_campaigns_accepts_each_intent(client: TestClient, intent_value: str) -> None:
    with client:
        response = client.get(f"/campaigns?intent={intent_value}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_campaigns_accepts_lead_actor_id_filter(client: TestClient) -> None:
    lead_id = uuid4()
    with client:
        response = client.get(f"/campaigns?lead_actor_id={lead_id}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_campaigns_accepts_subject_id_filter(client: TestClient) -> None:
    subject_id = uuid4()
    with client:
        response = client.get(f"/campaigns?subject_id={subject_id}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_campaigns_accepts_tag_filter(client: TestClient) -> None:
    with client:
        response = client.get("/campaigns?tag=operando")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_campaigns_accepts_combined_filters(client: TestClient) -> None:
    with client:
        response = client.get("/campaigns?status=Active&intent=Series&tag=hexapod")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_campaigns_rejects_unknown_status_with_422(client: TestClient) -> None:
    """'Inactive' is NOT in the Literal."""
    with client:
        response = client.get("/campaigns?status=Inactive")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_campaigns_rejects_unknown_intent_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/campaigns?intent=Cosmic")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_campaigns_rejects_invalid_cursor_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/campaigns?cursor=this-is-not-a-valid-cursor")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_campaigns_rejects_limit_zero_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/campaigns?limit=0")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_campaigns_rejects_limit_above_cap_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/campaigns?limit=101")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_campaigns_rejects_empty_tag_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/campaigns?tag=")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_campaigns_returns_403_when_authorize_denies() -> None:
    """Route documents 403 in `responses=`; this pins the wire-level path."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    def _override() -> ListCampaignsHandler:
        return fake_handler  # type: ignore[return-value]

    app.dependency_overrides[_get_list_campaigns_handler] = _override
    with TestClient(app) as fastapi_client:
        response = fastapi_client.get("/campaigns")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
