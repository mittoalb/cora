"""Contract tests for `Idempotency-Key` support on `POST /supplies`.

Same cross-BC `with_idempotency` decorator as the other create-style
slices. Test keys are short to stay below the gitleaks generic-API-
key entropy threshold.
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_post_supplies_without_key_creates_distinct_supplies_on_each_call() -> None:
    with TestClient(create_app()) as client:
        body = {
            "kind": "LiquidNitrogen",
            "name": "2-BM LN2",
            "facility_code": "cora",
        }
        r1 = client.post("/supplies", json=body)
        r2 = client.post("/supplies", json=body)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["supply_id"] != r2.json()["supply_id"]


@pytest.mark.contract
def test_post_supplies_same_key_and_body_returns_same_supply_id() -> None:
    with TestClient(create_app()) as client:
        body = {
            "kind": "LiquidNitrogen",
            "name": "2-BM LN2",
            "facility_code": "cora",
        }
        headers = {"Idempotency-Key": "sk-1"}
        r1 = client.post("/supplies", json=body, headers=headers)
        r2 = client.post("/supplies", json=body, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["supply_id"] == r2.json()["supply_id"]


@pytest.mark.contract
def test_post_supplies_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "sk-2"}
        r1 = client.post(
            "/supplies",
            json={
                "kind": "LiquidNitrogen",
                "name": "X",
                "facility_code": "cora",
            },
            headers=headers,
        )
        r2 = client.post(
            "/supplies",
            json={
                "kind": "PhotonBeam",
                "name": "X",
                "facility_code": "cora",
            },
            headers=headers,
        )

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()
