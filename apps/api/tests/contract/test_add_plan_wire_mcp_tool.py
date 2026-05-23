"""Contract tests for the `add_plan_wire` and `remove_plan_wire` MCP tools."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_add_plan_wire_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "add_plan_wire" in tool_names
    assert "remove_plan_wire" in tool_names


@pytest.mark.contract
def test_mcp_add_plan_wire_tool_returns_iserror_for_unknown_plan() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "add_plan_wire",
                    "arguments": {
                        "plan_id": str(uuid4()),
                        "source_asset_id": str(uuid4()),
                        "source_port_name": "trigger_out",
                        "target_asset_id": str(uuid4()),
                        "target_port_name": "trigger_in",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_remove_plan_wire_tool_returns_iserror_for_unknown_plan() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "remove_plan_wire",
                    "arguments": {
                        "plan_id": str(uuid4()),
                        "source_asset_id": str(uuid4()),
                        "source_port_name": "trigger_out",
                        "target_asset_id": str(uuid4()),
                        "target_port_name": "trigger_in",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
