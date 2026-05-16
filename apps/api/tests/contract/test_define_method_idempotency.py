"""Contract tests for `Idempotency-Key` support on `POST /methods`.

Same cross-BC `with_idempotency` decorator as the other create-style
slices. The capabilities_needed frozenset is normalized through
`_normalize_for_hash` (Trust 3c precedent) so reordered input
produces the same hash, and same body returns the same method_id.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_post_methods_without_key_creates_distinct_methods_on_each_call() -> None:
    with TestClient(create_app()) as client:
        r1 = client.post(
            "/methods",
            json={"name": "XRF Mapping", "capabilities_needed": []},
        )
        r2 = client.post(
            "/methods",
            json={"name": "XRF Mapping", "capabilities_needed": []},
        )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["method_id"] != r2.json()["method_id"]


@pytest.mark.contract
def test_post_methods_same_key_and_body_returns_same_method_id() -> None:
    cap1 = str(uuid4())
    body = {"name": "XRF Mapping", "capabilities_needed": [cap1]}
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "mk-1"}
        r1 = client.post("/methods", json=body, headers=headers)
        r2 = client.post("/methods", json=body, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["method_id"] == r2.json()["method_id"]


@pytest.mark.contract
def test_post_methods_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "mk-2"}
        r1 = client.post(
            "/methods",
            json={"name": "XRF Mapping", "capabilities_needed": []},
            headers=headers,
        )
        r2 = client.post(
            "/methods",
            json={"name": "Other", "capabilities_needed": []},
            headers=headers,
        )

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_methods_same_key_reordered_capabilities_returns_same_method_id() -> None:
    """Frozenset semantics: capabilities_needed is set-equal regardless
    of input order. The cross-BC `_normalize_for_hash` helper sorts
    frozensets before SHA256 hashing (locked in Trust 3c) so reordered
    input is treated as the same logical body. Pinned end-to-end."""
    cap1 = str(uuid4())
    cap2 = str(uuid4())
    cap3 = str(uuid4())
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "mk-3"}
        r1 = client.post(
            "/methods",
            json={"name": "X", "capabilities_needed": [cap1, cap2, cap3]},
            headers=headers,
        )
        r2 = client.post(
            "/methods",
            json={"name": "X", "capabilities_needed": [cap3, cap1, cap2]},
            headers=headers,
        )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["method_id"] == r2.json()["method_id"]


@pytest.mark.contract
def test_post_methods_different_keys_create_distinct_methods() -> None:
    with TestClient(create_app()) as client:
        r1 = client.post(
            "/methods",
            json={"name": "X", "capabilities_needed": []},
            headers={"Idempotency-Key": "mk-A"},
        )
        r2 = client.post(
            "/methods",
            json={"name": "X", "capabilities_needed": []},
            headers={"Idempotency-Key": "mk-B"},
        )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["method_id"] != r2.json()["method_id"]


@pytest.mark.contract
def test_post_methods_cached_response_returns_valid_uuid() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "mk-uuid"}
        r1 = client.post(
            "/methods",
            json={"name": "X", "capabilities_needed": []},
            headers=headers,
        )
        r2 = client.post(
            "/methods",
            json={"name": "X", "capabilities_needed": []},
            headers=headers,
        )

    UUID(r1.json()["method_id"])  # parses
    UUID(r2.json()["method_id"])  # parses
    assert r1.json()["method_id"] == r2.json()["method_id"]
