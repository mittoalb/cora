"""Contract tests for `POST /surfaces` + `GET /surfaces/{id}`.

End-to-end via TestClient(create_app()) so the full FastAPI stack
runs: body validation, authz (AllowAll), handler, event-store
append, response model. Mirror of `test_define_zone_idempotency.py`
structure but covers both define + get in one file.
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _body(name: str = "System HTTP", kind: str = "http") -> dict[str, str]:
    return {"name": name, "kind": kind}


@pytest.mark.contract
def test_post_surfaces_returns_201_and_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/surfaces", json=_body())
    assert response.status_code == 201
    body = response.json()
    assert "surface_id" in body
    UUID(body["surface_id"])  # parses as UUID


@pytest.mark.contract
def test_post_surfaces_persists_kind_value() -> None:
    """Each closed-enum kind round-trips through the wire layer."""
    with TestClient(create_app()) as client:
        for kind in ("http", "mcp_stdio", "mcp_streamable_http"):
            response = client.post("/surfaces", json=_body(name=f"Test {kind}", kind=kind))
            assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_surfaces_rejects_unknown_kind_with_422() -> None:
    """Closed enum: 'a2a' / 'websocket' / 'grpc' etc all 422."""
    with TestClient(create_app()) as client:
        for bad in ("a2a", "websocket", "grpc", "rest", ""):
            response = client.post("/surfaces", json=_body(kind=bad))
            assert response.status_code == 422, f"kind={bad!r} should 422"


@pytest.mark.contract
def test_post_surfaces_rejects_empty_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/surfaces", json=_body(name=""))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_surfaces_rejects_oversized_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/surfaces", json=_body(name="a" * 201))
    assert response.status_code == 422


@pytest.mark.contract
def test_get_surface_returns_200_after_define() -> None:
    with TestClient(create_app()) as client:
        defined = client.post("/surfaces", json=_body())
        surface_id = defined.json()["surface_id"]
        response = client.get(f"/surfaces/{surface_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == surface_id
    assert body["name"] == "System HTTP"
    assert body["kind"] == "http"
    assert body["status"] == "Defined"
    # Lifecycle timestamps are not on the Surface response shape
    # (Path C carve-out for singleton aggregate); see
    # surface/state.py docstring.
    assert "versioned_at" not in body
    assert "deprecated_at" not in body
    assert "defined_at" not in body


@pytest.mark.contract
def test_get_surface_returns_404_when_missing() -> None:
    missing = "01900000-0000-7000-8000-deadbeef0050"
    with TestClient(create_app()) as client:
        response = client.get(f"/surfaces/{missing}")
    assert response.status_code == 404
    assert missing in response.json()["detail"]


@pytest.mark.contract
def test_get_surface_rejects_invalid_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/surfaces/not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_post_surfaces_idempotency_key_returns_same_id_on_retry() -> None:
    headers = {"Idempotency-Key": "test-key-surface-1"}
    with TestClient(create_app()) as client:
        r1 = client.post("/surfaces", json=_body(), headers=headers)
        r2 = client.post("/surfaces", json=_body(), headers=headers)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["surface_id"] == r2.json()["surface_id"]


@pytest.mark.contract
def test_post_surfaces_idempotency_key_with_different_body_returns_422() -> None:
    headers = {"Idempotency-Key": "test-key-surface-2"}
    with TestClient(create_app()) as client:
        r1 = client.post("/surfaces", json=_body(), headers=headers)
        r2 = client.post("/surfaces", json=_body(name="Other"), headers=headers)
    assert r1.status_code == 201
    assert r2.status_code == 422
