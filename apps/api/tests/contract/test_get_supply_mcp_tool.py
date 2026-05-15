"""Contract tests for the `get_supply` MCP tool.

Verifies the iter-3 cleanup: tool returns SupplyOutput on hit and
raises ValueError -> isError on miss (FastMCP isError convention),
NOT silent None (which would render as `structuredContent: null`).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_supply_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    """Seed a supply via the MCP tool (not REST) so the contract test
    exercises the full MCP write surface. Mirrors capability's
    `_define_capability_via_tool` pattern."""
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {
                "name": "register_supply",
                "arguments": {
                    "scope": "Beamline",
                    "kind": "LiquidNitrogen",
                    "name": "35-BM LN2",
                },
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["supply_id"])


@pytest.mark.contract
def test_mcp_lists_get_supply_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "get_supply" in tool_names


@pytest.mark.contract
def test_mcp_get_supply_tool_returns_structured_supply_on_hit() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        supply_id = _register_supply_via_tool(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_supply",
                    "arguments": {"supply_id": str(supply_id)},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    sc = result["structuredContent"]
    assert sc["id"] == str(supply_id)
    assert sc["scope"] == "Beamline"
    assert sc["kind"] == "LiquidNitrogen"
    assert sc["name"] == "35-BM LN2"
    assert sc["status"] == "Unknown"


@pytest.mark.contract
def test_mcp_get_supply_tool_iserror_on_miss() -> None:
    """Iter-3 cleanup: handler returns None -> tool raises ValueError -> isError: true.
    Mirrors get_capability / get_asset convention; no silent None to LLM."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_supply",
                    "arguments": {"supply_id": str(uuid4())},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "not found" in result["content"][0]["text"].lower()
