"""Contract tests for the `list_policies` MCP tool.

Pin: tool surface (name in `tools/list`) and structured-output shape
on an empty database (`{items: [], next_cursor: None}`). Real
projection-populated paths live in the integration suite.
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_list_policies_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "list_policies" in tool_names


@pytest.mark.contract
def test_list_policies_mcp_tool_returns_structured_output_shape() -> None:
    """Empty database -> structured output `{items: [], next_cursor: None}`."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "list_policies", "arguments": {}},
            },
            headers=headers,
        )

    body = parse_sse_data(response.text)
    structured = body["result"]["structuredContent"]
    assert structured == {"items": [], "next_cursor": None}
