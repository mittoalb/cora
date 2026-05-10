"""Contract tests for the `X-Principal-Id` header.

Three concerns:
  1. **Optional**: existing tests that don't set the header continue
     to pass (fallback to SYSTEM_PRINCIPAL_ID). One test pins this.
  2. **Validated**: malformed UUIDs in the header surface as 422.
  3. **End-to-end with TrustAuthorize**: when TrustAuthorize is wired
     and a policy permits a specific principal, requests with that
     principal's UUID in the header succeed (201/200) while requests
     WITHOUT the header (or with a non-permitted principal) get 403.
     This is the load-bearing test that proves the full chain works:
     header → get_principal_id → handler kwarg → Authorize port →
     TrustAuthorize → load_policy → evaluate → Allow/Deny → HTTP
     status.
"""

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
# `app.state.deps.event_store` is typed as `Any` by FastAPI's state
# machinery; the white-box seed helper accepts that and casts at use.

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.event_envelope import to_new_event
from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    event_type_name,
    to_payload,
)

# ---------- Optional / validation ----------


@pytest.mark.contract
def test_post_actors_works_without_x_principal_id_header() -> None:
    """Pin the Phase 1 fallback: no header → SYSTEM_PRINCIPAL_ID,
    AllowAllAuthorize allows. Existing tests rely on this."""
    with TestClient(create_app()) as client:
        response = client.post("/actors", json={"name": "Doga"})
    assert response.status_code == 201


@pytest.mark.contract
def test_post_actors_accepts_explicit_x_principal_id_header() -> None:
    """Header IS extracted and used (passed to handler kwarg). Under
    AllowAllAuthorize the request still succeeds; the header's effect
    is verified end-to-end in the TrustAuthorize tests below."""
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            "/actors",
            json={"name": "Doga"},
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_actors_rejects_malformed_x_principal_id_with_422() -> None:
    """Pydantic UUID validation surfaces a 422 before the handler runs."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/actors",
            json={"name": "Doga"},
            headers={"X-Principal-Id": "not-a-uuid"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_zones_accepts_x_principal_id_header_in_trust_bc_too() -> None:
    """Trust BC's get_principal_id mirrors Access's; both honour
    X-Principal-Id. Pin so a future divergence is caught."""
    pid = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            "/zones",
            json={"name": "Detector"},
            headers={"X-Principal-Id": pid},
        )
    assert response.status_code == 201


# ---------- End-to-end with TrustAuthorize ----------


def _seed_policy_in_store(
    app: FastAPI,
    *,
    policy_id: UUID,
    conduit_id: UUID,
    permitted_principals: frozenset[UUID],
    permitted_commands: frozenset[str],
) -> None:
    """Seed a PolicyDefined event directly into the running app's
    in-memory store. Bypasses the API because TrustAuthorize is
    already gating every command at this point in the test (the
    bootstrap chicken-and-egg documented in TrustAuthorize's
    docstring)."""
    event = PolicyDefined(
        policy_id=policy_id,
        name="Test-policy",
        conduit_id=conduit_id,
        permitted_principals=list(permitted_principals),
        permitted_commands=list(permitted_commands),
        occurred_at=datetime.now(tz=UTC),
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=uuid4(),
        command_name="DefinePolicy",
        correlation_id=uuid4(),
    )
    store = app.state.deps.event_store
    asyncio.run(store.append("Policy", policy_id, 0, [new_event]))


@pytest.fixture
def trust_authorize_app(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, UUID, UUID]]:
    """Spin up an app with TrustAuthorize wired against a freshly
    seeded permissive policy. Yields (client, allowed_principal_id,
    policy_id).

    The seeded policy permits ONE principal to issue all the commands
    used in these tests. Every other principal (including the
    SYSTEM_PRINCIPAL_ID fallback when no header is sent) gets Deny.
    """
    policy_id = UUID("01900000-0000-7000-8000-00000000700f")
    allowed_principal = UUID("01900000-0000-7000-8000-000000000a01")
    # Post-3h: handlers pass nil conduit_id by default; the gating
    # policy must use the same conduit_id to match.
    conduit_id = UUID(int=0)

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TRUST_POLICY_ID", str(policy_id))

    client = TestClient(create_app())
    client.__enter__()  # start lifespan; app.state.deps now populated

    _seed_policy_in_store(
        # `client.app` is typed as `ASGI3App | _WrapASGI2` (Starlette);
        # we know it's the FastAPI instance create_app() returned. Cast
        # so pyright accepts the call.
        cast("FastAPI", client.app),
        policy_id=policy_id,
        conduit_id=conduit_id,
        permitted_principals=frozenset({allowed_principal}),
        permitted_commands=frozenset(
            {"RegisterActor", "DefineZone", "DefineConduit", "DefinePolicy"}
        ),
    )
    try:
        yield client, allowed_principal, policy_id
    finally:
        client.__exit__(None, None, None)


@pytest.mark.contract
def test_x_principal_id_matching_policy_returns_201(
    trust_authorize_app: tuple[TestClient, UUID, UUID],
) -> None:
    """End-to-end Allow path: header sets the principal_id that
    TrustAuthorize evaluates against the seeded policy → Allow → 201."""
    client, allowed_principal, _ = trust_authorize_app
    response = client.post(
        "/actors",
        json={"name": "Doga"},
        headers={"X-Principal-Id": str(allowed_principal)},
    )
    assert response.status_code == 201


@pytest.mark.contract
def test_x_principal_id_not_in_policy_returns_403(
    trust_authorize_app: tuple[TestClient, UUID, UUID],
) -> None:
    """End-to-end Deny path: a different principal in the header
    fails the policy's permitted_principals check → Deny → 403."""
    client, _, _ = trust_authorize_app
    other_principal = UUID("01900000-0000-7000-8000-000000000a02")
    response = client.post(
        "/actors",
        json={"name": "Doga"},
        headers={"X-Principal-Id": str(other_principal)},
    )
    assert response.status_code == 403


@pytest.mark.contract
def test_missing_x_principal_id_falls_back_to_system_and_is_denied(
    trust_authorize_app: tuple[TestClient, UUID, UUID],
) -> None:
    """No header → SYSTEM_PRINCIPAL_ID fallback → SYSTEM is NOT in
    the permitted_principals → Deny → 403. Important production
    guard: deployments without an auth proxy effectively run as
    SYSTEM, which (under a real policy) gets nothing."""
    client, _, _ = trust_authorize_app
    response = client.post("/actors", json={"name": "Doga"})
    assert response.status_code == 403
