"""Contract tests for the `deactivate_actor` MCP tool.

Mirrors test_register_actor_mcp_tool.py: full JSON-RPC handshake then
tool/call against the FastMCP-mounted endpoint with in-memory wiring.
"""

import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def _parse_sse_data(text: str) -> dict[str, Any]:
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[len("data:") :].strip())
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
    headers = {**_HEADERS, "mcp-session-id": session_id}
    notif = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=headers,
    )
    assert notif.status_code == 202
    return headers


def _register_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    """Helper: register via MCP and return the new actor's id."""
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "register_actor",
                "arguments": {"name": "Doga"},
            },
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = _parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    return UUID(body["result"]["structuredContent"]["actor_id"])


@pytest.mark.contract
def test_mcp_lists_deactivate_actor_tool() -> None:
    with TestClient(create_app()) as client:
        headers = _open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = _parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "deactivate_actor" in tool_names


@pytest.mark.contract
def test_mcp_deactivate_actor_tool_succeeds_for_active_actor() -> None:
    with TestClient(create_app()) as client:
        headers = _open_session(client)
        actor_id = _register_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "deactivate_actor",
                    "arguments": {"actor_id": str(actor_id)},
                },
            },
            headers=headers,
        )
    assert response.status_code == 200
    body = _parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_deactivate_actor_tool_returns_iserror_for_unknown_actor() -> None:
    with TestClient(create_app()) as client:
        headers = _open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "deactivate_actor",
                    "arguments": {"actor_id": str(uuid4())},
                },
            },
            headers=headers,
        )
    body = _parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_deactivate_actor_tool_returns_iserror_when_already_deactivated() -> None:
    with TestClient(create_app()) as client:
        headers = _open_session(client)
        actor_id = _register_via_tool(client, headers)

        # Deactivate once -> success.
        first = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "deactivate_actor",
                    "arguments": {"actor_id": str(actor_id)},
                },
            },
            headers=headers,
        )
        assert _parse_sse_data(first.text)["result"]["isError"] is False

        # Deactivate again -> isError.
        second = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "deactivate_actor",
                    "arguments": {"actor_id": str(actor_id)},
                },
            },
            headers=headers,
        )
    body = _parse_sse_data(second.text)
    assert body["result"]["isError"] is True
    assert "already deactivated" in body["result"]["content"][0]["text"].lower()
