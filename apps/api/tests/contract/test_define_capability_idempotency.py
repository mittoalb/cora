"""Contract tests for `Idempotency-Key` support on `POST /capabilities`.

Same cross-BC `with_idempotency` decorator as the other create-style
slices. Both `required_affordances` AND `executor_shapes` frozensets
are normalized through `_normalize_for_hash` (Trust 3c precedent) so
reordered input produces the same hash, and same body returns the
same capability_id.
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _body(
    code: str = "cora.capability.flyscan",
    name: str = "FlyScan",
    required_affordances: list[str] | None = None,
    executor_shapes: list[str] | None = None,
) -> dict[str, object]:
    return {
        "code": code,
        "name": name,
        "required_affordances": required_affordances or [],
        "executor_shapes": executor_shapes or ["Method"],
    }


@pytest.mark.contract
def test_post_capabilities_without_key_creates_distinct_each_call() -> None:
    with TestClient(create_app()) as client:
        r1 = client.post("/capabilities", json=_body())
        r2 = client.post("/capabilities", json=_body())
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["capability_id"] != r2.json()["capability_id"]


@pytest.mark.contract
def test_post_capabilities_same_key_and_body_returns_same_capability_id() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ck-1"}
        r1 = client.post("/capabilities", json=_body(), headers=headers)
        r2 = client.post("/capabilities", json=_body(), headers=headers)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["capability_id"] == r2.json()["capability_id"]


@pytest.mark.contract
def test_post_capabilities_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ck-2"}
        r1 = client.post("/capabilities", json=_body(name="X"), headers=headers)
        r2 = client.post("/capabilities", json=_body(name="Y"), headers=headers)
    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_capabilities_same_key_reordered_affordances_returns_same_id() -> None:
    """Frozenset semantics: required_affordances is set-equal regardless
    of input order. _normalize_for_hash sorts frozensets before SHA256."""
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ck-3"}
        r1 = client.post(
            "/capabilities",
            json=_body(required_affordances=["Rotatable", "Triggerable", "Homeable"]),
            headers=headers,
        )
        r2 = client.post(
            "/capabilities",
            json=_body(required_affordances=["Homeable", "Triggerable", "Rotatable"]),
            headers=headers,
        )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["capability_id"] == r2.json()["capability_id"]


@pytest.mark.contract
def test_post_capabilities_same_key_reordered_executor_shapes_returns_same_id() -> None:
    """Same frozenset-normalization for executor_shapes."""
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ck-4"}
        r1 = client.post(
            "/capabilities",
            json=_body(executor_shapes=["Method", "Procedure"]),
            headers=headers,
        )
        r2 = client.post(
            "/capabilities",
            json=_body(executor_shapes=["Procedure", "Method"]),
            headers=headers,
        )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["capability_id"] == r2.json()["capability_id"]


@pytest.mark.contract
def test_post_capabilities_different_keys_create_distinct_capabilities() -> None:
    with TestClient(create_app()) as client:
        r1 = client.post(
            "/capabilities",
            json=_body(code="cora.capability.a"),
            headers={"Idempotency-Key": "ck-A"},
        )
        r2 = client.post(
            "/capabilities",
            json=_body(code="cora.capability.b"),
            headers={"Idempotency-Key": "ck-B"},
        )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["capability_id"] != r2.json()["capability_id"]
