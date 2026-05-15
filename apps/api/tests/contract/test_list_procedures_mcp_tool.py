"""Contract tests for the `list_procedures` MCP tool."""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_list_procedures_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "list_procedures" in tool_names


@pytest.mark.contract
def test_mcp_list_procedures_tool_returns_empty_page_no_data() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "list_procedures", "arguments": {}},
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    structured = body["result"]["structuredContent"]
    assert structured["items"] == []
    assert structured["next_cursor"] is None
