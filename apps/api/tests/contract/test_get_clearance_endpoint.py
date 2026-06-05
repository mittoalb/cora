"""Contract tests for `GET /clearances/{clearance_id}`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _seed_clearance(client: TestClient, **overrides: object) -> str:
    body: dict[str, object] = {
        "kind": "ESAF",
        "facility_asset_id": str(uuid4()),
        "title": "Pilot ESAF for 2-BM",
        "bindings": [{"kind": "Run", "id": str(uuid4())}],
    }
    body.update(overrides)
    response = client.post("/clearances", json=body)
    assert response.status_code == 201
    return str(response.json()["clearance_id"])


@pytest.mark.contract
def test_get_clearances_returns_200_with_full_state() -> None:
    with TestClient(create_app()) as client:
        cid = _seed_clearance(
            client,
            risk_band="Yellow",
            external_id="ESAF-12345",
        )
        response = client.get(f"/clearances/{cid}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == cid
    assert body["kind"] == "ESAF"
    assert body["title"] == "Pilot ESAF for 2-BM"
    assert body["risk_band"] == "Yellow"
    assert body["external_id"] == "ESAF-12345"
    assert body["status"] == "Defined"
    assert body["review_steps"] == []
    assert body["parent_clearance_id"] is None


@pytest.mark.contract
def test_get_clearances_returns_404_when_not_found() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/clearances/{uuid4()}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.contract
def test_get_clearances_returns_422_for_malformed_uuid_path_param() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/clearances/not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_clearances_returns_bindings_with_kind_discriminator() -> None:
    with TestClient(create_app()) as client:
        sid, rid = str(uuid4()), str(uuid4())
        body = {
            "kind": "ESAF",
            "facility_asset_id": str(uuid4()),
            "title": "Multi",
            "bindings": [
                {"kind": "Subject", "id": sid},
                {"kind": "Run", "id": rid},
                {"kind": "External", "scheme": "proposal", "id": "GUP-12345"},
            ],
        }
        post_response = client.post("/clearances", json=body)
        cid = post_response.json()["clearance_id"]
        response = client.get(f"/clearances/{cid}")
    assert response.status_code == 200
    bindings = response.json()["bindings"]
    binding_kinds = {b["kind"] for b in bindings}
    assert binding_kinds == {"Subject", "Run", "External"}


@pytest.mark.contract
def test_get_clearances_returns_declarations_with_classifications() -> None:
    with TestClient(create_app()) as client:
        sid = str(uuid4())
        body: dict[str, object] = {
            "kind": "ESAF",
            "facility_asset_id": str(uuid4()),
            "title": "With hazards",
            "bindings": [{"kind": "Subject", "id": sid}],
            "declarations": [
                {
                    "target": {"kind": "Subject", "id": sid},
                    "classifications": [
                        {
                            "kind": "NFPA704",
                            "health": 2,
                            "flammability": 1,
                            "instability": 0,
                            "special": None,
                        },
                        {"kind": "RiskBand", "band": "Yellow"},
                    ],
                    "mitigations": ["ppe:gloves"],
                    "notes": "test",
                }
            ],
        }
        post_response = client.post("/clearances", json=body)
        cid = post_response.json()["clearance_id"]
        response = client.get(f"/clearances/{cid}")
    assert response.status_code == 200
    declarations = response.json()["declarations"]
    assert len(declarations) == 1
    decl = declarations[0]
    assert decl["target"]["kind"] == "Subject"
    classification_kinds = {c["kind"] for c in decl["classifications"]}
    assert classification_kinds == {"NFPA704", "RiskBand"}
    assert "ppe:gloves" in decl["mitigations"]
    assert decl["notes"] == "test"
