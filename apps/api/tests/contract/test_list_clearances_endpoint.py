"""Contract tests for `GET /clearances`.

Pins the response shape + filter query-param wiring. The actual
projection-fold behavior is exercised by
`tests/integration/test_list_clearances_handler_postgres.py`; this
file only exercises the route surface (status codes, schema,
authz wiring).
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_get_clearances_returns_200_with_empty_items_when_no_data() -> None:
    """In-memory projection-less app returns an empty page (no pool wired)."""
    with TestClient(create_app()) as client:
        response = client.get("/clearances")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


@pytest.mark.contract
def test_get_clearances_rejects_invalid_kind_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/clearances?kind=Mystery")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_clearances_rejects_invalid_status_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/clearances?status=Mystery")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_clearances_rejects_invalid_risk_band_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/clearances?risk_band=Purple")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_clearances_rejects_limit_above_100_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/clearances?limit=101")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_clearances_rejects_limit_below_1_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/clearances?limit=0")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_clearances_accepts_full_filter_set() -> None:
    """All 8 filters provided at once should parse cleanly (returns empty list)."""
    sid, aid, rid, pid = (uuid4() for _ in range(4))
    with TestClient(create_app()) as client:
        response = client.get(
            "/clearances",
            params={
                "kind": "ESAF",
                "status": "Active",
                "risk_band": "Yellow",
                "facility_code": "cora",
                "binds_to_subject_id": str(sid),
                "binds_to_asset_id": str(aid),
                "binds_to_run_id": str(rid),
                "binds_to_procedure_id": str(pid),
                "limit": "25",
            },
        )
    assert response.status_code == 200
    assert response.json()["items"] == []
