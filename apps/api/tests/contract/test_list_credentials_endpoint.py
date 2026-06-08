"""Contract tests for `GET /federation/credentials`.

Pins the response shape + filter query-param wiring. The actual
projection-fold behavior is exercised by the integration tier; this
file only exercises the route surface (status codes, schema,
filter parsing).

Vault-hygiene invariant: opaque secret material refs
(`secret_ref`, `public_material_ref`, `rotation_pending_*_ref`)
MUST NOT appear in this endpoint's response schema; `get_credential`
is the path for ref inspection.
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_get_credentials_returns_200_with_empty_items_when_no_data() -> None:
    """In-memory projection-less app returns an empty page (no pool wired)."""
    with TestClient(create_app()) as client:
        response = client.get("/federation/credentials")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


@pytest.mark.contract
def test_get_credentials_rejects_invalid_purpose_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/credentials?purpose=Mystery")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_credentials_rejects_invalid_status_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/credentials?status=Mystery")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_credentials_rejects_limit_above_100_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/credentials?limit=101")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_credentials_rejects_limit_below_1_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/credentials?limit=0")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_credentials_accepts_full_filter_set() -> None:
    """All 3 filters provided at once should parse cleanly (empty list)."""
    with TestClient(create_app()) as client:
        response = client.get(
            "/federation/credentials",
            params={
                "facility_code": "aps-2bm",
                "purpose": "Signing",
                "status": "Active",
                "limit": "25",
            },
        )
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.contract
def test_get_credentials_accepts_each_purpose_value() -> None:
    """Every CredentialPurpose value in the closed enum must parse."""
    purposes = [
        "Signing",
        "Verification",
        "Authentication",
        "Encryption",
        "SealOnlineSigning",
        "SealOfflineRoot",
    ]
    with TestClient(create_app()) as client:
        for purpose in purposes:
            response = client.get(f"/federation/credentials?purpose={purpose}")
            assert response.status_code == 200, purpose


@pytest.mark.contract
def test_get_credentials_accepts_each_status_value() -> None:
    """Every CredentialStatus value in the closed enum must parse."""
    statuses = ["Active", "Rotating", "Revoked"]
    with TestClient(create_app()) as client:
        for status_value in statuses:
            response = client.get(f"/federation/credentials?status={status_value}")
            assert response.status_code == 200, status_value


@pytest.mark.contract
def test_get_credentials_response_schema_omits_opaque_secret_refs() -> None:
    """Vault hygiene: opaque secret/public/rotation_pending refs MUST NOT
    appear in the response schema for this endpoint."""
    with TestClient(create_app()) as client:
        spec = client.get("/openapi.json").json()
    summary_dto = spec["components"]["schemas"]["CredentialSummaryDTO"]
    forbidden = {
        "secret_ref",
        "public_material_ref",
        "rotation_pending_secret_ref",
        "rotation_pending_public_material_ref",
    }
    assert forbidden.isdisjoint(summary_dto["properties"].keys())
