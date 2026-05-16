"""Contract tests for `Idempotency-Key` support on `POST /campaigns`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _body(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "test",
        "intent": "InSitu",
        "lead_actor_id": str(uuid4()),
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_post_campaigns_without_key_creates_distinct_campaigns_on_each_call() -> None:
    with TestClient(create_app()) as client:
        body = _body()
        r1 = client.post("/campaigns", json=body)
        r2 = client.post("/campaigns", json=body)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["campaign_id"] != r2.json()["campaign_id"]


@pytest.mark.contract
def test_post_campaigns_same_key_and_body_returns_same_campaign_id() -> None:
    with TestClient(create_app()) as client:
        body = _body()
        headers = {"Idempotency-Key": "cp-1"}
        r1 = client.post("/campaigns", json=body, headers=headers)
        r2 = client.post("/campaigns", json=body, headers=headers)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["campaign_id"] == r2.json()["campaign_id"]


@pytest.mark.contract
def test_post_campaigns_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "cp-2"}
        r1 = client.post(
            "/campaigns",
            json=_body(name="first"),
            headers=headers,
        )
        r2 = client.post(
            "/campaigns",
            json=_body(name="different"),
            headers=headers,
        )
    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()
