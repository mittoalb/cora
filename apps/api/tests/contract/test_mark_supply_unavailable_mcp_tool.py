"""Contract tests for the `mark_supply_unavailable` MCP tool (10a-b)."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_supply_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {
                "name": "register_supply",
                "arguments": {
                    "kind": "LiquidNitrogen",
                    "name": "2-BM LN2",
                    "facility_code": "cora",
                },
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["supply_id"])


@pytest.mark.contract
def test_mcp_lists_mark_supply_unavailable_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "mark_supply_unavailable" in tool_names


@pytest.mark.contract
def test_mcp_mark_supply_unavailable_tool_succeeds_from_unknown() -> None:
    """`mark_supply_unavailable` accepts the widest source set
    (Unknown / Available / Degraded / Recovering); pin the Unknown case."""
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
                    "name": "mark_supply_unavailable",
                    "arguments": {
                        "supply_id": str(supply_id),
                        "reason": "beam dump",
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["supply_id"] == str(supply_id)
