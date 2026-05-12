"""Contract tests for the `list_actors` MCP tool.

Pin: tool surface (name, description, structured output shape) and
cursor handling. Real projection-populated path is in the integration
suite.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("APP_ENV", "test")
    return TestClient(create_app())


def _mcp_initialize(client: TestClient) -> str:
    """Open an MCP session; return the session ID for follow-up calls."""
    response = client.post(
        "/mcp/",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        },
        headers={"Accept": "application/json, text/event-stream"},
    )
    assert response.status_code == 200, response.text
    session_id = response.headers.get("mcp-session-id", "")
    assert session_id
    # Drain initialize response.
    return session_id


def _mcp_call(
    client: TestClient,
    session_id: str,
    method: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.post(
        "/mcp/",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": method,
            "params": params or {},
        },
        headers={
            "Accept": "application/json, text/event-stream",
            "mcp-session-id": session_id,
        },
    )
    assert response.status_code == 200, response.text
    # Server may stream SSE; parse the first data: line.
    body = response.text
    for line in body.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: ") :])
    return json.loads(body)


@pytest.mark.contract
def test_list_actors_tool_appears_in_tools_list(client: TestClient) -> None:
    with client:
        session_id = _mcp_initialize(client)
        # initialized notification
        client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers={
                "Accept": "application/json, text/event-stream",
                "mcp-session-id": session_id,
            },
        )
        result = _mcp_call(client, session_id, "tools/list")

    assert "result" in result
    tools: list[dict[str, Any]] = result["result"]["tools"]
    names: set[str] = {str(tool["name"]) for tool in tools}
    assert "list_actors" in names


@pytest.mark.contract
def test_list_actors_tool_returns_structured_output_shape(
    client: TestClient,
) -> None:
    """Empty database -> structured output `{items: [], next_cursor: None}`."""
    with client:
        session_id = _mcp_initialize(client)
        client.post(
            "/mcp/",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers={
                "Accept": "application/json, text/event-stream",
                "mcp-session-id": session_id,
            },
        )
        result = _mcp_call(
            client,
            session_id,
            "tools/call",
            {"name": "list_actors", "arguments": {}},
        )

    structured: dict[str, Any] = result["result"]["structuredContent"]
    assert structured == {"items": [], "next_cursor": None}
