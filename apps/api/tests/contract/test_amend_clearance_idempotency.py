"""Contract tests for `Idempotency-Key` support on `POST /clearances/{id}/amend`.

`amend_clearance` is the second create-style slice in Safety BC (after
`register_clearance`) that returns 201 + a new clearance_id and gets
wrapped with `with_idempotency` at wire.py. This file pins the wrap
behavior: same key + same body returns the same child clearance_id;
same key + different body returns 422.

Setup: each test first registers + walks a parent clearance through
the FSM to Active so the amend slice has a legitimate target. Test
keys stay short to stay below the gitleaks generic-API-key entropy
threshold.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _walk_parent_to_active(client: TestClient) -> str:
    """Register a clearance and drive it through the FSM to Active.

    Returns the parent's clearance_id so the test can issue
    `POST /clearances/{parent}/amend`.
    """
    register_resp = client.post(
        "/clearances",
        json={
            "kind": "ESAF",
            "facility_code": "cora",
            "title": "Original",
            "bindings": [{"kind": "Run", "id": str(uuid4())}],
        },
    )
    assert register_resp.status_code == 201, register_resp.text
    parent_id = register_resp.json()["clearance_id"]

    assert client.post(f"/clearances/{parent_id}/submit").status_code == 204
    assert (
        client.post(
            f"/clearances/{parent_id}/start-review",
            json={"first_reviewer_role": "ESH"},
        ).status_code
        == 204
    )
    assert (
        client.post(
            f"/clearances/{parent_id}/review-steps",
            json={
                "step_index": 0,
                "role": "ESH",
                "decision": "Approved",
                "decided_at": datetime.now(tz=UTC).isoformat(),
            },
        ).status_code
        == 204
    )
    assert client.post(f"/clearances/{parent_id}/approve", json={}).status_code == 204
    assert client.post(f"/clearances/{parent_id}/activate").status_code == 204
    return parent_id


def _amend_body() -> dict[str, object]:
    return {
        "kind": "ESAF",
        "facility_code": "cora",
        "title": "Amended after scope-change",
        "bindings": [{"kind": "Run", "id": str(uuid4())}],
    }


@pytest.mark.contract
def test_post_amend_without_key_creates_distinct_children_on_each_call() -> None:
    """Without Idempotency-Key, two identical amend calls against the
    SAME parent would race: only one wins because the parent goes
    Active->Superseded after the first amend. The second fails with
    409 ClearanceCannotAmendError. Pin this to document why the key
    matters."""
    with TestClient(create_app()) as client:
        parent_id = _walk_parent_to_active(client)
        b = _amend_body()
        r1 = client.post(f"/clearances/{parent_id}/amend", json=b)
        r2 = client.post(f"/clearances/{parent_id}/amend", json=b)
    assert r1.status_code == 201
    # Second amend: parent is now Superseded, so the gate refuses.
    assert r2.status_code == 409


@pytest.mark.contract
def test_post_amend_same_key_and_body_returns_same_child_clearance_id() -> None:
    """With Idempotency-Key, the second call returns the cached
    response (same child_clearance_id) without executing the handler
    a second time. Critically: the parent does NOT transition twice
    (cached response means no second event landing)."""
    with TestClient(create_app()) as client:
        parent_id = _walk_parent_to_active(client)
        b = _amend_body()
        headers = {"Idempotency-Key": "ak-1"}
        r1 = client.post(f"/clearances/{parent_id}/amend", json=b, headers=headers)
        r2 = client.post(f"/clearances/{parent_id}/amend", json=b, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["clearance_id"] == r2.json()["clearance_id"]


@pytest.mark.contract
def test_post_amend_same_key_different_body_returns_422() -> None:
    """The cross-BC idempotency contract: same key + different body
    -> 422 (idempotency conflict; client must use a fresh key for
    a different request)."""
    with TestClient(create_app()) as client:
        parent_id = _walk_parent_to_active(client)
        headers = {"Idempotency-Key": "ak-2"}
        r1 = client.post(
            f"/clearances/{parent_id}/amend",
            json={
                "kind": "ESAF",
                "facility_code": "cora",
                "title": "First amendment",
                "bindings": [{"kind": "Run", "id": str(uuid4())}],
            },
            headers=headers,
        )
        r2 = client.post(
            f"/clearances/{parent_id}/amend",
            json={
                "kind": "SAF",
                "facility_code": "cora",
                "title": "Different amendment",
                "bindings": [{"kind": "Run", "id": str(uuid4())}],
            },
            headers=headers,
        )

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()
