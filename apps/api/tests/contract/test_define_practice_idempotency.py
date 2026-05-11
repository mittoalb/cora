"""Contract tests for `Idempotency-Key` support on `POST /practices`.

Same cross-BC `with_idempotency` decorator as the other create-style
slices. Test keys are short to stay below the gitleaks generic-API-
key entropy threshold.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_post_practices_without_key_creates_distinct_practices_on_each_call() -> None:
    body = {"name": "X", "method_id": str(uuid4()), "site_id": str(uuid4())}
    with TestClient(create_app()) as client:
        r1 = client.post("/practices", json=body)
        r2 = client.post("/practices", json=body)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["practice_id"] != r2.json()["practice_id"]


@pytest.mark.contract
def test_post_practices_same_key_and_body_returns_same_practice_id() -> None:
    body = {"name": "X", "method_id": str(uuid4()), "site_id": str(uuid4())}
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "pk-1"}
        r1 = client.post("/practices", json=body, headers=headers)
        r2 = client.post("/practices", json=body, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["practice_id"] == r2.json()["practice_id"]


@pytest.mark.contract
def test_post_practices_same_key_different_body_returns_422() -> None:
    method_id = str(uuid4())
    site_id = str(uuid4())
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "pk-2"}
        r1 = client.post(
            "/practices",
            json={"name": "X", "method_id": method_id, "site_id": site_id},
            headers=headers,
        )
        r2 = client.post(
            "/practices",
            json={"name": "Y", "method_id": method_id, "site_id": site_id},
            headers=headers,
        )

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_practices_different_keys_create_distinct_practices() -> None:
    body = {"name": "X", "method_id": str(uuid4()), "site_id": str(uuid4())}
    with TestClient(create_app()) as client:
        r1 = client.post("/practices", json=body, headers={"Idempotency-Key": "pk-A"})
        r2 = client.post("/practices", json=body, headers={"Idempotency-Key": "pk-B"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["practice_id"] != r2.json()["practice_id"]


@pytest.mark.contract
def test_post_practices_cached_response_returns_valid_uuid() -> None:
    body = {"name": "X", "method_id": str(uuid4()), "site_id": str(uuid4())}
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "pk-uuid"}
        r1 = client.post("/practices", json=body, headers=headers)
        r2 = client.post("/practices", json=body, headers=headers)

    UUID(r1.json()["practice_id"])  # parses
    UUID(r2.json()["practice_id"])  # parses
    assert r1.json()["practice_id"] == r2.json()["practice_id"]
