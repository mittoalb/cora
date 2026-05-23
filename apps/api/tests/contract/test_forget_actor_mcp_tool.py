"""Contract tests for the `forget_actor` MCP tool.

Drives the FastMCP-mounted PII-erasure tool over its JSON-RPC
protocol. The full handshake is required (`initialize` →
`notifications/initialized` → `tools/call`); shared helpers live in
`tests/contract/_mcp_helpers.py`.
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import HEADERS, open_session, parse_sse_data


def _register_actor_via_mcp(client: TestClient, session_headers: dict[str, str]) -> UUID:
    """Helper: register an actor over the MCP register_actor tool so
    the subsequent forget_actor call has a target."""
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {
                "name": "register_actor",
                "arguments": {"name": "Doga"},
            },
        },
        headers=session_headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["actor_id"])


@pytest.mark.contract
def test_mcp_lists_forget_actor_tool() -> None:
    """The forget_actor tool is registered on the MCP server."""
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
    assert "forget_actor" in tool_names


@pytest.mark.contract
def test_mcp_forget_actor_tool_succeeds_for_existing_actor() -> None:
    """Round-trip: register an actor over MCP, then erase via the
    forget_actor tool. Successful tool calls return isError=False
    with no structured content (the handler returns None)."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        actor_id = _register_actor_via_mcp(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "forget_actor",
                    "arguments": {"actor_id": str(actor_id)},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"].get("isError") is not True, body


@pytest.mark.contract
def test_mcp_forget_actor_tool_returns_iserror_for_unknown_actor() -> None:
    """No prior register -> ActorNotFoundError surfaces as
    isError=True with a text diagnostic."""
    unknown_id = "01900000-0000-7000-8000-0000000000ff"
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "forget_actor",
                    "arguments": {"actor_id": unknown_id},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_forget_actor_tool_rejects_invalid_uuid_argument() -> None:
    """FastMCP schema validation rejects non-UUID arguments before
    reaching the handler."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "forget_actor",
                    "arguments": {"actor_id": "not-a-uuid"},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_initialize_returns_server_info() -> None:
    """Sanity: the MCP handshake works at all (mirrors the
    register_actor_mcp_tool test, included so the slice file has
    a basic standalone health-check too)."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "contract-test", "version": "0.1"},
                },
            },
            headers=HEADERS,
        )
    assert response.status_code == 200
    assert "mcp-session-id" in response.headers
