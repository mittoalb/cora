"""Contract tests for `GET /methods/{method_id}`.

Mirrors `test_get_capability_endpoint.py`. Pinned response shape:
`{id, name, needs_capabilities, status}`. needs_capabilities is a
sorted list of UUIDs (deterministic ordering).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _define_method(
    client: TestClient,
    *,
    name: str = "XRF Mapping",
    needs_capabilities: list[str] | None = None,
) -> UUID:
    response = client.post(
        "/methods",
        json={
            "name": name,
            "needs_capabilities": needs_capabilities if needs_capabilities is not None else [],
        },
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["method_id"])


@pytest.mark.contract
def test_get_method_returns_200_with_defined_status_for_new_method() -> None:
    cap1 = str(uuid4())
    cap2 = str(uuid4())
    with TestClient(create_app()) as client:
        method_id = _define_method(
            client,
            name="XRF Fly Mapping",
            needs_capabilities=[cap1, cap2],
        )
        response = client.get(f"/methods/{method_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(method_id)
    assert body["name"] == "XRF Fly Mapping"
    assert body["status"] == "Defined"
    # Sorted by UUID string form (deterministic).
    assert body["needs_capabilities"] == sorted([cap1, cap2])
    # Null until version_method runs (6b).
    assert body["version"] is None


@pytest.mark.contract
def test_get_method_returns_empty_needs_capabilities_for_procedural_method() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client, name="Sample Cleaning", needs_capabilities=[])
        response = client.get(f"/methods/{method_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["needs_capabilities"] == []


@pytest.mark.contract
def test_get_method_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/methods/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert "not found" in body["detail"].lower()


@pytest.mark.contract
def test_get_method_returns_422_for_malformed_method_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/methods/not-a-uuid")
    assert response.status_code == 422
