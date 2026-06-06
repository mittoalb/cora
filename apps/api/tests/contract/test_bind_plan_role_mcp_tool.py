"""Contract tests for the `bind_plan_role` MCP tool. Slice 2."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data
from tests.contract.test_bind_plan_role_endpoint import (
    setup_plan_with_role as _setup,
)


@pytest.mark.contract
def test_mcp_lists_bind_plan_role_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "bind_plan_role" in tool_names


@pytest.mark.contract
def test_mcp_bind_plan_role_tool_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        ctx = _setup(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "bind_plan_role",
                    "arguments": {
                        "plan_id": str(UUID(ctx["plan_id"])),
                        "role_name": "detector",
                        "asset_id": str(UUID(ctx["asset_id"])),
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
