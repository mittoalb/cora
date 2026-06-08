"""Contract tests for `GET /federation/permits/{permit_id}`.

In-memory `TestClient(create_app())` runs without a Postgres pool, so
the real handler always raises `PermitNotFoundError`. The 200 happy
path is exercised via `app.dependency_overrides` injecting a fake
handler that returns a synthesized `PermitView`; the 404 + 422 paths
ride the real handler + the BC's exception-handler chain.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.errors import UnauthorizedError
from cora.federation.features.get_permit.handler import PermitView
from cora.federation.features.get_permit.route import (
    _get_handler as _get_get_permit_handler,  # pyright: ignore[reportPrivateUsage]
)

_T_DEFINED = datetime(2026, 5, 30, 10, 0, 0, tzinfo=UTC)
_T_ACTIVATED = datetime(2026, 5, 30, 11, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_PERMIT_ID = UUID("01900000-0000-7000-8000-000000fed901")
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-00000000c001")
_ACTOR_ID = UUID("01900000-0000-7000-8000-000000000099")


def _outbound_view() -> PermitView:
    return PermitView(
        permit_id=_PERMIT_ID,
        peer_facility_code="aps-2bm",
        direction="Outbound",
        allowed_credential_ids=[_CREDENTIAL_ID],
        allowed_payload_types=["application/vnd.cora.dataset+json"],
        allowed_artifact_kinds=["dataset"],
        abi_tier_floor="Stable",
        expires_at=_EXPIRES_AT,
        defined_by=_ACTOR_ID,
        status="Active",
        terms_kind="Outbound",
        read_scope="ReadAllArtifacts",
        onward_action_scope="ReadOnly",
        scopes=[{"kind": "dataset", "name": "alpha", "qualifier": None}],
        accepted_canonicalization_versions=None,
        required_receipt_kinds=None,
        publisher_grant_correlation_handle=None,
        inbound_allowed_artifact_kinds=None,
        defined_at=_T_DEFINED,
        activated_at=_T_ACTIVATED,
        suspended_at=None,
        resumed_at=None,
        revoked_at=None,
    )


def _inbound_view() -> PermitView:
    return PermitView(
        permit_id=_PERMIT_ID,
        peer_facility_code="aps-2bm",
        direction="Inbound",
        allowed_credential_ids=[_CREDENTIAL_ID],
        allowed_payload_types=["application/vnd.cora.dataset+json"],
        allowed_artifact_kinds=["dataset"],
        abi_tier_floor="Stable",
        expires_at=_EXPIRES_AT,
        defined_by=_ACTOR_ID,
        status="Defined",
        terms_kind="Inbound",
        read_scope=None,
        onward_action_scope=None,
        scopes=None,
        accepted_canonicalization_versions=["v1"],
        required_receipt_kinds=["signed"],
        publisher_grant_correlation_handle="grant-abc",
        inbound_allowed_artifact_kinds=["dataset"],
        defined_at=_T_DEFINED,
        activated_at=None,
        suspended_at=None,
        resumed_at=None,
        revoked_at=None,
    )


@pytest.mark.contract
def test_get_federation_permit_returns_200_with_outbound_terms() -> None:
    app = create_app()
    view = _outbound_view()

    async def fake_handler(*args: object, **kwargs: object) -> PermitView:
        _ = (args, kwargs)
        return view

    app.dependency_overrides[_get_get_permit_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get(f"/federation/permits/{_PERMIT_ID}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(_PERMIT_ID)
    assert body["peer_facility_code"] == "aps-2bm"
    assert body["direction"] == "Outbound"
    assert body["status"] == "Active"
    assert body["allowed_credential_ids"] == [str(_CREDENTIAL_ID)]
    assert body["defined_by"] == str(_ACTOR_ID)
    assert body["terms"]["kind"] == "Outbound"
    assert body["terms"]["read_scope"] == "ReadAllArtifacts"
    assert body["terms"]["onward_action_scope"] == "ReadOnly"
    assert body["terms"]["scopes"] == [{"kind": "dataset", "name": "alpha", "qualifier": None}]
    assert body["defined_at"].startswith("2026-05-30T10:00:00")
    assert body["activated_at"].startswith("2026-05-30T11:00:00")
    assert body["suspended_at"] is None
    assert body["revoked_at"] is None


@pytest.mark.contract
def test_get_federation_permit_returns_200_with_inbound_terms() -> None:
    app = create_app()
    view = _inbound_view()

    async def fake_handler(*args: object, **kwargs: object) -> PermitView:
        _ = (args, kwargs)
        return view

    app.dependency_overrides[_get_get_permit_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get(f"/federation/permits/{_PERMIT_ID}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["direction"] == "Inbound"
    assert body["terms"]["kind"] == "Inbound"
    assert body["terms"]["accepted_canonicalization_versions"] == ["v1"]
    assert body["terms"]["required_receipt_kinds"] == ["signed"]
    assert body["terms"]["publisher_grant_correlation_handle"] == "grant-abc"
    assert body["terms"]["inbound_allowed_artifact_kinds"] == ["dataset"]
    assert body["activated_at"] is None


@pytest.mark.contract
def test_get_federation_permit_returns_404_when_not_found() -> None:
    """No pool wired in-memory -> real handler raises PermitNotFoundError -> 404."""
    with TestClient(create_app()) as client:
        response = client.get(f"/federation/permits/{uuid4()}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.contract
def test_get_federation_permit_returns_422_for_malformed_path_uuid() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/federation/permits/not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_federation_permit_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_get_permit_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get(f"/federation/permits/{uuid4()}")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
