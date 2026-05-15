"""Idempotency-Key contract tests for `POST /procedures`.

Mirrors the cross-BC idempotency contract: same key + same body
returns the cached procedure_id; same key + different body returns
422 (IdempotencyConflictError mapped to 422 by Access).
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_repeat_same_key_same_body_returns_cached_procedure_id() -> None:
    key = "test-idempotency-key-procedure-1"
    body = {"name": "Vessel-A bakeout", "kind": "bakeout"}
    with TestClient(create_app()) as client:
        first = client.post("/procedures", json=body, headers={"Idempotency-Key": key})
        second = client.post("/procedures", json=body, headers={"Idempotency-Key": key})
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["procedure_id"] == second.json()["procedure_id"]


@pytest.mark.contract
def test_repeat_same_key_different_body_returns_422() -> None:
    key = "test-idempotency-key-procedure-2"
    with TestClient(create_app()) as client:
        first = client.post(
            "/procedures",
            json={"name": "Vessel-A bakeout", "kind": "bakeout"},
            headers={"Idempotency-Key": key},
        )
        second = client.post(
            "/procedures",
            json={"name": "Vessel-B bakeout", "kind": "bakeout"},
            headers={"Idempotency-Key": key},
        )
    assert first.status_code == 201
    assert second.status_code == 422


@pytest.mark.contract
def test_different_keys_create_distinct_procedures() -> None:
    body = {"name": "Vessel-A bakeout", "kind": "bakeout"}
    with TestClient(create_app()) as client:
        first = client.post(
            "/procedures",
            json=body,
            headers={"Idempotency-Key": "key-A-" + str(uuid4())},
        )
        second = client.post(
            "/procedures",
            json=body,
            headers={"Idempotency-Key": "key-B-" + str(uuid4())},
        )
    assert first.json()["procedure_id"] != second.json()["procedure_id"]


@pytest.mark.contract
def test_no_key_creates_new_procedure_each_call() -> None:
    body = {"name": "Vessel-A bakeout", "kind": "bakeout"}
    with TestClient(create_app()) as client:
        first = client.post("/procedures", json=body)
        second = client.post("/procedures", json=body)
    assert first.json()["procedure_id"] != second.json()["procedure_id"]
