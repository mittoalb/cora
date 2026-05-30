"""Contract tests for the `get_permit` MCP tool.

In-memory `TestClient(create_app())` runs without a Postgres pool, so
the real handler always raises `PermitNotFoundError` (surfaces as
`isError: true` on the tool envelope). The happy path is exercised
by overriding the bound handler on `app.state.federation.get_permit`
after lifespan startup; the tools/list registration test rides the
real wiring.
"""

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.features.get_permit.handler import Handler, PermitView
from tests.contract._mcp_helpers import open_session, parse_sse_data

_T_DEFINED = datetime(2026, 5, 30, 10, 0, 0, tzinfo=UTC)
_T_ACTIVATED = datetime(2026, 5, 30, 11, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_PERMIT_ID = UUID("01900000-0000-7000-8000-000000fed901")
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-00000000c001")
_ACTOR_ID = UUID("01900000-0000-7000-8000-000000000099")


def _outbound_view() -> PermitView:
    return PermitView(
        permit_id=_PERMIT_ID,
        peer_facility_id="aps-2bm",
        direction="Outbound",
        allowed_credentials=[_CREDENTIAL_ID],
        allowed_payload_types=["application/vnd.cora.dataset+json"],
        permitted_artifact_kinds=["dataset"],
        abi_tier_floor="Stable",
        expires_at=_EXPIRES_AT,
        defined_by_actor_id=_ACTOR_ID,
        status="Active",
        terms_kind="Outbound",
        read_scope="ReadAllArtifacts",
        onward_action_scope="ReadOnly",
        scope_set=[{"kind": "dataset", "name": "alpha", "qualifier": None}],
        accepted_canonicalization_versions=None,
        required_receipt_kinds=None,
        publisher_grant_correlation_handle=None,
        allowed_artifact_kinds=None,
        defined_at=_T_DEFINED,
        activated_at=_T_ACTIVATED,
        suspended_at=None,
        resumed_at=None,
        revoked_at=None,
    )


def _override_handler(app: object, handler: Handler) -> None:
    """Override the MCP-bound handler bundle so the tool returns the fake."""
    state = cast("object", app.state.federation)  # type: ignore[attr-defined]
    object.__setattr__(state, "get_permit", handler)


@pytest.mark.contract
def test_mcp_lists_get_permit_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "get_permit" in tool_names


@pytest.mark.contract
def test_mcp_get_permit_tool_returns_structured_state_on_hit() -> None:
    """Happy path via handler override: tool returns the full structured PermitView."""
    app = create_app()
    view = _outbound_view()

    async def fake_handler(*args: object, **kwargs: object) -> PermitView:
        _ = (args, kwargs)
        return view

    with TestClient(app) as client:
        _override_handler(app, cast("Handler", fake_handler))
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_permit",
                    "arguments": {"permit_id": str(_PERMIT_ID)},
                },
            },
            headers=headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    payload = result["structuredContent"]
    assert payload["id"] == str(_PERMIT_ID)
    assert payload["direction"] == "Outbound"
    assert payload["status"] == "Active"
    assert payload["terms"]["kind"] == "Outbound"
    assert payload["terms"]["read_scope"] == "ReadAllArtifacts"
    assert payload["terms"]["onward_action_scope"] == "ReadOnly"


@pytest.mark.contract
def test_mcp_get_permit_tool_returns_iserror_for_unknown_permit() -> None:
    """No pool wired in-memory -> real handler raises PermitNotFoundError -> isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_permit",
                    "arguments": {"permit_id": str(uuid4())},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_get_permit_tool_rejects_missing_required_argument() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "get_permit",
                    "arguments": {},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
