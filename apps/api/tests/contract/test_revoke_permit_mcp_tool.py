"""Contract tests for the `revoke_permit` MCP tool.

Widest-source terminal transition: any non-Revoked permit ->
Revoked. Strict-not-idempotent: re-revoking surfaces as MCP
`isError: true` (mapped from `PermitCannotRevokeError`).
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_args() -> dict[str, Any]:
    return {
        "peer_facility_id": "aps-2bm",
        "direction": "Outbound",
        "allowed_credentials": [str(uuid4())],
        "allowed_payload_types": ["application/json"],
        "permitted_artifact_kinds": ["dataset"],
        "abi_tier_floor": "Stable",
        "expires_at": "2030-01-01T00:00:00+00:00",
        "terms": {
            "kind": "Outbound",
            "scope_set": [{"kind": "dataset", "name": "public", "qualifier": None}],
            "read_scope": "ReadAllArtifacts",
            "onward_action_scope": "ReadOnly",
        },
    }


def _register_permit_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {"name": "register_permit", "arguments": _register_args()},
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False, body
    return UUID(body["result"]["structuredContent"]["permit_id"])


@pytest.mark.contract
def test_mcp_lists_revoke_permit_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "revoke_permit" in tool_names


@pytest.mark.contract
def test_mcp_revoke_permit_tool_succeeds_from_defined() -> None:
    """`revoke_permit` accepts any non-Revoked status; pin the Defined case
    (no intervening transitions)."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        permit_id = _register_permit_via_tool(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "revoke_permit",
                    "arguments": {"permit_id": str(permit_id)},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["permit_id"] == str(permit_id)


@pytest.mark.contract
def test_mcp_revoke_permit_tool_is_strict_not_idempotent() -> None:
    """Re-revoke surfaces as `isError: true` (mapped from PermitCannotRevokeError)."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        permit_id = _register_permit_via_tool(client, session_headers)
        first = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "revoke_permit",
                    "arguments": {"permit_id": str(permit_id)},
                },
            },
            headers=session_headers,
        )
        assert parse_sse_data(first.text)["result"]["isError"] is False
        second = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "revoke_permit",
                    "arguments": {"permit_id": str(permit_id)},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(second.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_revoke_permit_tool_returns_iserror_for_unknown_permit() -> None:
    """Calling `revoke_permit` on an unknown id surfaces as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "revoke_permit",
                    "arguments": {"permit_id": str(uuid4())},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_revoke_permit_tool_rejects_missing_permit_id() -> None:
    """Pydantic-layer rejection bubbles as isError: true via FastMCP."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "revoke_permit", "arguments": {}},
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
