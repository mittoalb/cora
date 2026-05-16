"""Contract tests for `GET /cautions`.

End-to-end pagination/filter behavior against a real projection lives
in the integration suite. These tests pin the contract: empty page
when no data, status-code shape, parameter validation, and the
authorize-Deny -> 403 path.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.caution.errors import UnauthorizedError
from cora.caution.features.list_cautions.handler import Handler as ListCautionsHandler
from cora.caution.features.list_cautions.route import (
    _get_handler as _get_list_cautions_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


@pytest.mark.contract
def test_get_cautions_returns_empty_page_with_no_data(client: TestClient) -> None:
    with client:
        response = client.get("/cautions")
    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


@pytest.mark.contract
@pytest.mark.parametrize("target_kind_value", ["Asset", "Procedure"])
def test_get_cautions_accepts_each_target_kind(client: TestClient, target_kind_value: str) -> None:
    with client:
        response = client.get(f"/cautions?target_kind={target_kind_value}")
    assert response.status_code == 200


@pytest.mark.contract
@pytest.mark.parametrize(
    "category_value",
    [
        "Wear",
        "Calibration",
        "Wiring",
        "OperationalWindow",
        "InterlockQuirk",
        "ProcedureGotcha",
    ],
)
def test_get_cautions_accepts_each_category(client: TestClient, category_value: str) -> None:
    with client:
        response = client.get(f"/cautions?category={category_value}")
    assert response.status_code == 200


@pytest.mark.contract
@pytest.mark.parametrize("severity_value", ["Notice", "Caution", "Warning"])
def test_get_cautions_accepts_each_severity(client: TestClient, severity_value: str) -> None:
    with client:
        response = client.get(f"/cautions?severity={severity_value}")
    assert response.status_code == 200


@pytest.mark.contract
@pytest.mark.parametrize("min_severity_value", ["Notice", "Caution", "Warning"])
def test_get_cautions_accepts_each_min_severity(
    client: TestClient, min_severity_value: str
) -> None:
    with client:
        response = client.get(f"/cautions?min_severity={min_severity_value}")
    assert response.status_code == 200


@pytest.mark.contract
@pytest.mark.parametrize("status_value", ["Active", "Superseded", "Retired", "all"])
def test_get_cautions_accepts_each_status_including_all_sentinel(
    client: TestClient, status_value: str
) -> None:
    """Three concrete statuses + 'all' sentinel; design memo: default is Active,
    'all' to include Superseded + Retired. The route translates 'all' to None
    (no filter) and routes the rest as a single-element list."""
    with client:
        response = client.get(f"/cautions?status={status_value}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_cautions_accepts_multi_value_severity(client: TestClient) -> None:
    """`?severity=Caution&severity=Warning` is the multi-value any-of shape;
    the route forwards it as the canonical `severities` list."""
    with client:
        response = client.get("/cautions?severity=Caution&severity=Warning")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_cautions_accepts_multi_value_status(client: TestClient) -> None:
    """`?status=Active&status=Superseded` narrows to those two statuses;
    distinct from the `?status=all` sentinel that disables the filter."""
    with client:
        response = client.get("/cautions?status=Active&status=Superseded")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_cautions_rejects_severity_and_min_severity_together_with_422(
    client: TestClient,
) -> None:
    """Conflict guard: the old single-string SQL silently returned the empty
    intersection. The route now 422s."""
    with client:
        response = client.get("/cautions?severity=Caution&min_severity=Warning")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_cautions_rejects_status_all_mixed_with_explicit_with_422(
    client: TestClient,
) -> None:
    """`?status=all&status=Active` is ambiguous (disable filter OR narrow?);
    the route 422s rather than guessing."""
    with client:
        response = client.get("/cautions?status=all&status=Active")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_cautions_accepts_target_id_filter(client: TestClient) -> None:
    target_id = uuid4()
    with client:
        response = client.get(f"/cautions?target_id={target_id}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_cautions_accepts_author_actor_id_filter(client: TestClient) -> None:
    author_id = uuid4()
    with client:
        response = client.get(f"/cautions?author_actor_id={author_id}")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_cautions_accepts_tag_filter(client: TestClient) -> None:
    with client:
        response = client.get("/cautions?tag=hexapod")
    assert response.status_code == 200


@pytest.mark.contract
def test_get_cautions_accepts_combined_filters(client: TestClient) -> None:
    with client:
        response = client.get(
            "/cautions?target_kind=Asset&category=Wear&severity=Caution&status=Active&tag=hexapod"
        )
    assert response.status_code == 200


@pytest.mark.contract
def test_get_cautions_rejects_unknown_target_kind_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/cautions?target_kind=Run")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_cautions_rejects_unknown_category_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/cautions?category=Cosmic")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_cautions_rejects_unknown_severity_with_422(client: TestClient) -> None:
    """Lowercase 'warning' is NOT in the Literal."""
    with client:
        response = client.get("/cautions?severity=warning")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_cautions_rejects_unknown_status_with_422(client: TestClient) -> None:
    """'Inactive' is NOT in the Literal (Active / Superseded / Retired / all only)."""
    with client:
        response = client.get("/cautions?status=Inactive")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_cautions_rejects_invalid_cursor_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/cautions?cursor=this-is-not-a-valid-cursor")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_cautions_rejects_limit_zero_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/cautions?limit=0")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_cautions_rejects_limit_above_cap_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/cautions?limit=101")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_cautions_rejects_empty_tag_with_422(client: TestClient) -> None:
    with client:
        response = client.get("/cautions?tag=")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_cautions_returns_403_when_authorize_denies() -> None:
    """Route documents 403 in `responses=`; this pins the wire-level path."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    def _override() -> ListCautionsHandler:
        return fake_handler  # type: ignore[return-value]

    app.dependency_overrides[_get_list_cautions_handler] = _override
    with TestClient(app) as fastapi_client:
        response = fastapi_client.get("/cautions")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
