"""Contract tests for the `register_credential` MCP tool.

Pins tool registration, happy-path structured output (credential_id),
and error-path bubbling (isError true on missing args, on decider-
layer expiry rejection, and on whitespace-only secret_ref).
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC).isoformat()


def _args(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "facility_id": "aps-2bm",
        "audience": "peer.example.org",
        "purpose": "Signing",
        "secret_ref": "vault://kv/cora/federation/aps-2bm/signing#v1",
        "public_material_ref": "vault://kv/cora/federation/aps-2bm/signing/pub#v1",
        "expires_at": _EXPIRES_AT,
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_mcp_lists_register_credential_tool() -> None:
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
    assert "register_credential" in tool_names


@pytest.mark.contract
def test_mcp_register_credential_tool_returns_structured_credential_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "register_credential", "arguments": _args()},
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert "credential_id" in result["structuredContent"]
    UUID(result["structuredContent"]["credential_id"])


@pytest.mark.contract
def test_mcp_register_credential_tool_returns_iserror_on_expires_at_in_past() -> None:
    """Decider-layer CredentialExpiredError surfaces through FastMCP as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "register_credential",
                    "arguments": _args(
                        expires_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC).isoformat(),
                    ),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_register_credential_tool_returns_iserror_on_whitespace_only_secret_ref() -> None:
    """InvalidCredentialSecretRefError surfaces through FastMCP as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "register_credential",
                    "arguments": _args(secret_ref="   "),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_register_credential_tool_rejects_missing_required_argument() -> None:
    """Pydantic-layer rejection (facility_id missing) bubbles as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        args = _args()
        del args["facility_id"]
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "register_credential",
                    "arguments": args,
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
