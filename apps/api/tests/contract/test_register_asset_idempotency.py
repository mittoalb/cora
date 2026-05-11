"""Contract tests for `Idempotency-Key` support on `POST /assets`.

Same cross-BC `with_idempotency` decorator as the other create-style
slices. Test keys are short to stay below the gitleaks generic-API-
key entropy threshold.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _body(name: str = "APS-2BM", level: str = "Unit") -> dict[str, object]:
    return {"name": name, "level": level, "parent_id": str(uuid4())}


@pytest.mark.contract
def test_post_assets_without_key_creates_distinct_assets_on_each_call() -> None:
    with TestClient(create_app()) as client:
        # Use the same parent_id so only the Idempotency-Key absence
        # (not body diff) drives distinctness.
        body = _body()
        r1 = client.post("/assets", json=body)
        r2 = client.post("/assets", json=body)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["asset_id"] != r2.json()["asset_id"]


@pytest.mark.contract
def test_post_assets_same_key_and_body_returns_same_asset_id() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ak-1"}
        body = _body()
        r1 = client.post("/assets", json=body, headers=headers)
        r2 = client.post("/assets", json=body, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["asset_id"] == r2.json()["asset_id"]


@pytest.mark.contract
def test_post_assets_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ak-2"}
        r1 = client.post("/assets", json=_body(name="APS-2BM"), headers=headers)
        r2 = client.post("/assets", json=_body(name="Other"), headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_assets_different_keys_create_distinct_assets() -> None:
    with TestClient(create_app()) as client:
        body = _body()
        r1 = client.post("/assets", json=body, headers={"Idempotency-Key": "ak-A"})
        r2 = client.post("/assets", json=body, headers={"Idempotency-Key": "ak-B"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["asset_id"] != r2.json()["asset_id"]


@pytest.mark.contract
def test_post_assets_cached_response_returns_valid_uuid() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ak-uuid"}
        body = _body()
        r1 = client.post("/assets", json=body, headers=headers)
        r2 = client.post("/assets", json=body, headers=headers)

    UUID(r1.json()["asset_id"])  # parses
    UUID(r2.json()["asset_id"])  # parses
    assert r1.json()["asset_id"] == r2.json()["asset_id"]
