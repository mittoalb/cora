"""Contract tests for `Idempotency-Key` support on `POST /cautions/{id}/supersede`.

Mirrors `test_amend_clearance_idempotency.py` shape: each test first
seeds a parent caution (Active), then exercises the supersede flow.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _register_body(asset_id: str) -> dict[str, object]:
    return {
        "target": {"kind": "Asset", "id": asset_id},
        "category": "Wear",
        "severity": "Caution",
        "text": "original",
        "workaround": "original workaround",
    }


def _supersede_body(asset_id: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "target": {"kind": "Asset", "id": asset_id},
        "category": "Wear",
        "severity": "Caution",
        "text": "amended",
        "workaround": "amended workaround",
    }
    base.update(overrides)
    return base


def _seed_parent(client: TestClient, asset_id: str) -> str:
    response = client.post("/cautions", json=_register_body(asset_id))
    assert response.status_code == 201
    return str(response.json()["caution_id"])


@pytest.mark.contract
def test_post_supersede_without_key_second_call_409s_when_parent_already_superseded() -> None:
    """Without Idempotency-Key, the second supersede sees parent already
    Superseded -> CautionCannotSupersedeError -> 409. Documents why the
    key matters (mirrors amend_clearance idempotency contract test)."""
    with TestClient(create_app()) as client:
        asset_id = str(uuid4())
        parent_id = _seed_parent(client, asset_id)
        b = _supersede_body(asset_id)
        r1 = client.post(f"/cautions/{parent_id}/supersede", json=b)
        r2 = client.post(f"/cautions/{parent_id}/supersede", json=b)
    assert r1.status_code == 201
    assert r2.status_code == 409


@pytest.mark.contract
def test_post_supersede_same_key_and_body_returns_same_child_caution_id() -> None:
    with TestClient(create_app()) as client:
        asset_id = str(uuid4())
        parent_id = _seed_parent(client, asset_id)
        b = _supersede_body(asset_id)
        headers = {"Idempotency-Key": "sc-1"}
        r1 = client.post(f"/cautions/{parent_id}/supersede", json=b, headers=headers)
        r2 = client.post(f"/cautions/{parent_id}/supersede", json=b, headers=headers)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["caution_id"] == r2.json()["caution_id"]


@pytest.mark.contract
def test_post_supersede_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        asset_id = str(uuid4())
        parent_id = _seed_parent(client, asset_id)
        headers = {"Idempotency-Key": "sc-2"}
        r1 = client.post(
            f"/cautions/{parent_id}/supersede",
            json=_supersede_body(asset_id, text="first"),
            headers=headers,
        )
        r2 = client.post(
            f"/cautions/{parent_id}/supersede",
            json=_supersede_body(asset_id, text="different"),
            headers=headers,
        )
    assert r1.status_code == 201
    assert r2.status_code == 422
    assert "idempotency-key" in r2.json()["detail"].lower()
