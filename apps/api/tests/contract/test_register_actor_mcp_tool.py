"""Contract tests for the `register_actor` MCP tool.

Drives the FastMCP-mounted endpoint over its JSON-RPC protocol, with
the same in-memory wiring the contract tests for the REST endpoint use
(APP_ENV=test selects InMemoryEventStore via the lifespan).

The full MCP handshake is required:
    1. POST initialize    -> server returns mcp-session-id header
    2. POST notifications/initialized
    3. POST tools/call    -> the tool invocation
"""

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


def _parse_sse_data(text: str) -> dict[str, Any]:
    """Pull the JSON object out of an SSE response (the `data:` line)."""
    for line in text.splitlines():
        if line.startswith("data:"):
            payload = line[len("data:") :].strip()
            return json.loads(payload)
    msg = f"No SSE data: line in response body: {text!r}"
    raise AssertionError(msg)


def _open_session(client: TestClient) -> dict[str, str]:
    """Run initialize + notifications/initialized; return headers with session id."""
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
def test_mcp_initialize_returns_server_info() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
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
    assert response.status_code == 200
    assert "mcp-session-id" in response.headers
    body = _parse_sse_data(response.text)
    assert body["result"]["serverInfo"]["name"] == "cora"


@pytest.mark.contract
def test_mcp_lists_register_actor_tool() -> None:
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
    assert "register_actor" in tool_names


@pytest.mark.contract
def test_mcp_register_actor_tool_returns_structured_actor_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = _open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "register_actor",
                    "arguments": {"name": "Doga"},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = _parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert "actor_id" in result["structuredContent"]
    UUID(result["structuredContent"]["actor_id"])  # parses without raising


@pytest.mark.contract
def test_mcp_register_actor_tool_returns_iserror_on_invalid_input() -> None:
    """Whitespace-only name passes Pydantic min_length=1 but trips the
    domain VO; FastMCP wraps the raised InvalidActorNameError as
    isError: true with a text diagnostic."""
    with TestClient(create_app()) as client:
        session_headers = _open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "register_actor",
                    "arguments": {"name": "   "},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = _parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Actor name" in result["content"][0]["text"]


@pytest.mark.contract
def test_mcp_register_actor_tool_rejects_missing_argument() -> None:
    """Missing required `name` argument returns isError from FastMCP's schema validation."""
    with TestClient(create_app()) as client:
        session_headers = _open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "register_actor",
                    "arguments": {},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = _parse_sse_data(response.text)
    assert body["result"]["isError"] is True
