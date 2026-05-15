"""Contract tests for `Idempotency-Key` support on `POST /clearances`.

Same cross-BC `with_idempotency` decorator as the other create-style
slices. Test keys are short to stay below the gitleaks generic-API-key
entropy threshold.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _body() -> dict[str, object]:
    return {
        "kind": "ESAF",
        "facility_asset_id": str(uuid4()),
        "title": "Pilot ESAF",
        "bindings": [{"kind": "Run", "id": str(uuid4())}],
    }


@pytest.mark.contract
def test_post_clearances_without_key_creates_distinct_clearances_on_each_call() -> None:
    with TestClient(create_app()) as client:
        b = _body()
        r1 = client.post("/clearances", json=b)
        r2 = client.post("/clearances", json=b)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["clearance_id"] != r2.json()["clearance_id"]


@pytest.mark.contract
def test_post_clearances_same_key_and_body_returns_same_clearance_id() -> None:
    with TestClient(create_app()) as client:
        b = _body()
        headers = {"Idempotency-Key": "ck-1"}
        r1 = client.post("/clearances", json=b, headers=headers)
        r2 = client.post("/clearances", json=b, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["clearance_id"] == r2.json()["clearance_id"]


@pytest.mark.contract
def test_post_clearances_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ck-2"}
        r1 = client.post(
            "/clearances",
            json={
                "kind": "ESAF",
                "facility_asset_id": str(uuid4()),
                "title": "First",
                "bindings": [{"kind": "Run", "id": str(uuid4())}],
            },
            headers=headers,
        )
        r2 = client.post(
            "/clearances",
            json={
                "kind": "SAF",
                "facility_asset_id": str(uuid4()),
                "title": "Second",
                "bindings": [{"kind": "Run", "id": str(uuid4())}],
            },
            headers=headers,
        )

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()
