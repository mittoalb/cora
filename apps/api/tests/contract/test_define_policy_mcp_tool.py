"""Contract tests for the `define_policy` MCP tool."""

import json
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}

_CONDUIT = "01900000-0000-7000-8000-00000000aaaa"
_PRINCIPAL = "01900000-0000-7000-8000-000000000a01"


def _parse_sse_data(text: str) -> dict[str, Any]:
    for line in text.splitlines():
        if line.startswith("data:"):
            payload = line[len("data:") :].strip()
            return json.loads(payload)
    msg = f"No SSE data: line in response body: {text!r}"
    raise AssertionError(msg)


def _open_session(client: TestClient) -> dict[str, str]:
    init = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "contract-test", "version": "0.1"},
            },
        },
        headers=_HEADERS,
    )
    assert init.status_code == 200
    session_id = init.headers["mcp-session-id"]
    headers_with_session = {**_HEADERS, "mcp-session-id": session_id}
    notif = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=headers_with_session,
    )
    assert notif.status_code == 202
    return headers_with_session


@pytest.mark.contract
def test_mcp_lists_define_policy_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = _open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    assert response.status_code == 200
    body = _parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "define_policy" in tool_names


@pytest.mark.contract
def test_mcp_define_policy_tool_returns_structured_policy_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = _open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "define_policy",
                    "arguments": {
                        "name": "Beam-team",
                        "conduit_id": _CONDUIT,
                        "permitted_principals": [_PRINCIPAL],
                        "permitted_commands": ["RegisterActor"],
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = _parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert "policy_id" in result["structuredContent"]
    UUID(result["structuredContent"]["policy_id"])


@pytest.mark.contract
def test_mcp_define_policy_tool_returns_iserror_on_invalid_input() -> None:
    """Whitespace-only name passes Pydantic min_length=1 but trips the
    domain VO; FastMCP wraps the raised InvalidPolicyNameError."""
    with TestClient(create_app()) as client:
        session_headers = _open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "define_policy",
                    "arguments": {
                        "name": "   ",
                        "conduit_id": _CONDUIT,
                        "permitted_principals": [_PRINCIPAL],
                        "permitted_commands": ["RegisterActor"],
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = _parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Policy name" in result["content"][0]["text"]


@pytest.mark.contract
def test_mcp_define_policy_tool_rejects_missing_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = _open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "define_policy",
                    "arguments": {"name": "Beam-team"},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = _parse_sse_data(response.text)
    assert body["result"]["isError"] is True
