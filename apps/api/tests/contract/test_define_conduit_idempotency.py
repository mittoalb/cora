"""Contract tests for `Idempotency-Key` support on `POST /conduits`.

Mirror of `test_define_zone_idempotency.py`. Same cross-BC decorator
(`cora.infrastructure.idempotency.with_idempotency`) wrapped in
`cora.trust.wire.wire_trust`; this test verifies that header
extraction + per-BC error mapping work for the second slice on this
BC.
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_SOURCE = "01900000-0000-7000-8000-00000000aaaa"
_TARGET = "01900000-0000-7000-8000-00000000bbbb"


def _body(name: str = "Detector-to-Storage") -> dict[str, str]:
    return {
        "name": name,
        "source_zone_id": _SOURCE,
        "target_zone_id": _TARGET,
    }


@pytest.mark.contract
def test_post_conduits_without_key_creates_distinct_conduits_on_each_call() -> None:
    with TestClient(create_app()) as client:
        r1 = client.post("/conduits", json=_body())
        r2 = client.post("/conduits", json=_body())
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["conduit_id"] != r2.json()["conduit_id"]


@pytest.mark.contract
def test_post_conduits_same_key_and_body_returns_same_conduit_id() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ck-1"}
        r1 = client.post("/conduits", json=_body(), headers=headers)
        r2 = client.post("/conduits", json=_body(), headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["conduit_id"] == r2.json()["conduit_id"]


@pytest.mark.contract
def test_post_conduits_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ck-2"}
        r1 = client.post("/conduits", json=_body(), headers=headers)
        r2 = client.post("/conduits", json=_body(name="Other"), headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 422
    body = r2.json()
    assert "detail" in body
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_conduits_different_keys_create_distinct_conduits() -> None:
    with TestClient(create_app()) as client:
        r1 = client.post(
            "/conduits",
            json=_body(),
            headers={"Idempotency-Key": "ck-A"},
        )
        r2 = client.post(
            "/conduits",
            json=_body(),
            headers={"Idempotency-Key": "ck-B"},
        )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["conduit_id"] != r2.json()["conduit_id"]


@pytest.mark.contract
def test_post_conduits_cached_response_returns_valid_uuid() -> None:
    with TestClient(create_app()) as client:
        headers = {"Idempotency-Key": "ck-uuid"}
        r1 = client.post("/conduits", json=_body(), headers=headers)
        r2 = client.post("/conduits", json=_body(), headers=headers)

    UUID(r1.json()["conduit_id"])  # parses
    UUID(r2.json()["conduit_id"])  # parses
    assert r1.json()["conduit_id"] == r2.json()["conduit_id"]


@pytest.mark.contract
def test_post_conduits_idempotency_key_is_scoped_to_principal_not_to_slice() -> None:
    """Reusing an Idempotency-Key across different commands (here,
    /zones then /conduits) returns 422 — keys are scoped to
    `(principal_id, key)` per Stripe's pattern, NOT to
    `(principal_id, key, command_name)`. Both calls run as
    SYSTEM_PRINCIPAL_ID; the second hits the same cache entry, hashes
    the (different) command body, detects the mismatch, and raises
    IdempotencyConflictError -> 422.

    Pinned in a contract test so a future "scope keys per command"
    refactor (which would break this) has to do so deliberately and
    update the docs at the same time. Composite PK
    `(principal_id, key)` lives in `idempotency_keys` migration."""
    shared_key = "ck-shared"
    with TestClient(create_app()) as client:
        r_zone = client.post(
            "/zones",
            json={"name": "Detector"},
            headers={"Idempotency-Key": shared_key},
        )
        r_conduit = client.post(
            "/conduits",
            json=_body(),
            headers={"Idempotency-Key": shared_key},
        )
    assert r_zone.status_code == 201
    assert r_conduit.status_code == 422
