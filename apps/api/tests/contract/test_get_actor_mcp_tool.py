"""Contract tests for the `get_actor` MCP tool."""

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
    headers = {**_HEADERS, "mcp-session-id": init.headers["mcp-session-id"]}
    notif = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=headers,
    )
    assert notif.status_code == 202
    return headers


def _register_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
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
    body = _parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["actor_id"])


@pytest.mark.contract
def test_mcp_lists_get_actor_tool() -> None:
    with TestClient(create_app()) as client:
        headers = _open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = _parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "get_actor" in tool_names


@pytest.mark.contract
def test_mcp_get_actor_tool_returns_structured_actor_for_known_id() -> None:
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
                    "name": "get_actor",
                    "arguments": {"actor_id": str(actor_id)},
                },
            },
            headers=headers,
        )

    body = _parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["id"] == str(actor_id)
    assert structured["name"] == "Doga"
    assert structured["is_active"] is True


@pytest.mark.contract
def test_mcp_get_actor_tool_returns_iserror_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        headers = _open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_actor",
                    "arguments": {"actor_id": str(uuid4())},
                },
            },
            headers=headers,
        )

    body = _parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
