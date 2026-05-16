"""Contract tests for `GET /methods/{method_id}`.

Mirrors `test_get_capability_endpoint.py`. Pinned response shape:
`{id, name, capabilities_needed, status}`. capabilities_needed is a
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
    capabilities_needed: list[str] | None = None,
    supplies_needed: list[str] | None = None,
) -> UUID:
    body: dict[str, object] = {
        "name": name,
        "capabilities_needed": capabilities_needed if capabilities_needed is not None else [],
    }
    if supplies_needed is not None:
        body["supplies_needed"] = supplies_needed
    response = client.post("/methods", json=body)
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
            capabilities_needed=[cap1, cap2],
        )
        response = client.get(f"/methods/{method_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(method_id)
    assert body["name"] == "XRF Fly Mapping"
    assert body["status"] == "Defined"
    # Sorted by UUID string form (deterministic).
    assert body["capabilities_needed"] == sorted([cap1, cap2])
    # Null until version_method runs (6b).
    assert body["version"] is None


@pytest.mark.contract
def test_get_method_returns_empty_capabilities_needed_for_procedural_method() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client, name="Sample Cleaning", capabilities_needed=[])
        response = client.get(f"/methods/{method_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["capabilities_needed"] == []


# ---------- Phase 10b: supplies_needed on response ----------


@pytest.mark.contract
def test_get_method_returns_supplies_needed_sorted_lexically() -> None:
    """Phase 10b. Method.supplies_needed surfaces on the GET response
    as a sorted list of Supply.kind strings."""
    with TestClient(create_app()) as client:
        method_id = _define_method(
            client,
            name="Tomography",
            supplies_needed=["PhotonBeam", "LiquidNitrogen"],
        )
        response = client.get(f"/methods/{method_id}")

    assert response.status_code == 200
    body = response.json()
    # Sorted lexically (deterministic ordering, mirrors capabilities_needed convention).
    assert body["supplies_needed"] == ["LiquidNitrogen", "PhotonBeam"]


@pytest.mark.contract
def test_get_method_returns_empty_supplies_needed_when_unspecified() -> None:
    """Backward-compat: omit supplies_needed in POST body, response
    still includes the field as []. Pre-10b clients keep working."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client, name="X", capabilities_needed=[])
        response = client.get(f"/methods/{method_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["supplies_needed"] == []


@pytest.mark.contract
def test_define_method_returns_422_for_oversized_supply_kind() -> None:
    """Pydantic per-element max_length=50 catches at the boundary."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/methods",
            json={
                "name": "X",
                "capabilities_needed": [],
                "supplies_needed": ["x" * 51],
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_define_method_returns_422_for_empty_supply_kind() -> None:
    """Pydantic per-element min_length=1 catches at the boundary."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/methods",
            json={
                "name": "X",
                "capabilities_needed": [],
                "supplies_needed": [""],
            },
        )
    assert response.status_code == 422


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
