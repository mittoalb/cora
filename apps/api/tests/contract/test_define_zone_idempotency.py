"""Contract tests for `Idempotency-Key` support on `POST /zones`.

Same pattern as `test_register_actor_idempotency.py`. The wrap is
provided by the cross-BC `cora.infrastructure.idempotency` decorator
applied in `cora.trust.wire.wire_trust`; this test verifies that the
header-extraction + per-BC error mapping survive the second BC's
wiring.
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_post_zones_without_key_creates_distinct_zones_on_each_call() -> None:
    with TestClient(create_app()) as client:
        r1 = client.post("/zones", json={"name": "Detector"})
        r2 = client.post("/zones", json={"name": "Detector"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["zone_id"] != r2.json()["zone_id"]


@pytest.mark.contract
def test_post_zones_same_key_and_body_returns_same_zone_id() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "zone-test-key-1"}
        r1 = client.post("/zones", json={"name": "Detector"}, headers=headers)
        r2 = client.post("/zones", json={"name": "Detector"}, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["zone_id"] == r2.json()["zone_id"]


@pytest.mark.contract
def test_post_zones_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "zone-test-key-2"}
        r1 = client.post("/zones", json={"name": "Detector"}, headers=headers)
        r2 = client.post("/zones", json={"name": "Other"}, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_zones_different_keys_create_distinct_zones() -> None:
    with TestClient(create_app()) as client:
        r1 = client.post(
            "/zones",
            json={"name": "Detector"},
            headers={"Idempotency-Key": "zone-key-A"},
        )
        r2 = client.post(
            "/zones",
            json={"name": "Detector"},
            headers={"Idempotency-Key": "zone-key-B"},
        )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["zone_id"] != r2.json()["zone_id"]


@pytest.mark.contract
def test_post_zones_cached_response_returns_valid_uuid() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "zone-test-key-uuid"}
        r1 = client.post("/zones", json={"name": "Detector"}, headers=headers)
        r2 = client.post("/zones", json={"name": "Detector"}, headers=headers)

    UUID(r1.json()["zone_id"])  # parses
    UUID(r2.json()["zone_id"])  # parses
    assert r1.json()["zone_id"] == r2.json()["zone_id"]
