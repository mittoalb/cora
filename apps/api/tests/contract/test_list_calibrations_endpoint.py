"""Contract tests for `GET /calibrations`.

Pagination + filter-passthrough is exercised at the integration tier
(against a real Postgres-backed projection). These tests pin the
wire shape — pydantic argument validation, response envelope,
authorize denial.
"""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.calibration.errors import UnauthorizedError
from cora.calibration.features.list_calibrations.route import (
    _get_handler as _get_list_calibrations_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_get_calibrations_returns_empty_page_when_projection_empty() -> None:
    """In-memory test deps have no Postgres pool; handler returns empty."""
    with TestClient(create_app()) as client:
        response = client.get("/calibrations")
    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "next_cursor": None}


@pytest.mark.contract
def test_get_calibrations_accepts_quantity_filter() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/calibrations", params={"quantity": "rotation_center"})
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.contract
def test_get_calibrations_rejects_unknown_quantity_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/calibrations", params={"quantity": "rotation_centre"})
    assert response.status_code == 422


@pytest.mark.contract
def test_get_calibrations_accepts_subsystem_or_asset_id_filter() -> None:
    with TestClient(create_app()) as client:
        response = client.get(
            "/calibrations",
            params={"subsystem_or_asset_id": str(uuid4())},
        )
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.contract
def test_get_calibrations_accepts_multivalue_status_filter() -> None:
    with TestClient(create_app()) as client:
        # Use multi-value via the params tuple to send multiple ?latest_revision_status=...
        response = client.get(
            "/calibrations",
            params=[
                ("latest_revision_status", "Provisional"),
                ("latest_revision_status", "Verified"),
            ],
        )
    assert response.status_code == 200


@pytest.mark.contract
def test_get_calibrations_accepts_multivalue_source_kind_filter() -> None:
    with TestClient(create_app()) as client:
        response = client.get(
            "/calibrations",
            params=[
                ("latest_revision_source_kind", "measured"),
                ("latest_revision_source_kind", "computed"),
            ],
        )
    assert response.status_code == 200


@pytest.mark.contract
def test_get_calibrations_rejects_unknown_status_value_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get(
            "/calibrations",
            params={"latest_revision_status": "Refined"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_get_calibrations_rejects_limit_below_one_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/calibrations", params={"limit": 0})
    assert response.status_code == 422


@pytest.mark.contract
def test_get_calibrations_rejects_limit_above_cap_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/calibrations", params={"limit": 101})
    assert response.status_code == 422


@pytest.mark.contract
def test_get_calibrations_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> Any:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_list_calibrations_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get("/calibrations")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
