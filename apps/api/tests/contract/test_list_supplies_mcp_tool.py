"""Contract tests for the `list_supplies` MCP tool."""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_list_supplies_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "list_supplies" in tool_names


@pytest.mark.contract
def test_mcp_list_supplies_tool_returns_empty_page_with_no_data() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "list_supplies", "arguments": {}},
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    sc = result["structuredContent"]
    assert sc == {"items": [], "next_cursor": None}


@pytest.mark.contract
def test_mcp_list_supplies_tool_accepts_combined_filters() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "list_supplies",
                    "arguments": {
                        "scope": "Beamline",
                        "kind": "LiquidNitrogen",
                        "status": "Available",
                        "limit": 25,
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["items"] == []


@pytest.mark.contract
def test_mcp_list_supplies_tool_iserror_on_unknown_status() -> None:
    """Lowercase 'unknown' is NOT in the SupplyStatusFilter Literal."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "list_supplies",
                    "arguments": {"status": "unknown"},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
