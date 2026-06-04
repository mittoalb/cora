"""Contract tests for the `list_fixtures` MCP tool."""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_list_fixtures_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    tool_names = [t["name"] for t in parse_sse_data(response.text)["result"]["tools"]]
    assert "list_fixtures" in tool_names


@pytest.mark.contract
def test_mcp_list_fixtures_returns_page_shape() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "list_fixtures",
                    "arguments": {"limit": 10},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    out = body["result"]["structuredContent"]
    assert "items" in out
    assert "next_cursor" in out
    assert isinstance(out["items"], list)
