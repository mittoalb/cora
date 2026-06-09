"""Contract tests for the `mark_supply_recovering` MCP tool (10a-b)."""

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
                    "scope": "Beamline",
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


def _mark_unavailable_via_tool(
    client: TestClient, headers: dict[str, str], supply_id: UUID
) -> None:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 101,
            "method": "tools/call",
            "params": {
                "name": "mark_supply_unavailable",
                "arguments": {"supply_id": str(supply_id), "reason": "beam dump"},
            },
        },
        headers=headers,
    )
    assert parse_sse_data(response.text)["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_lists_mark_supply_recovering_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "mark_supply_recovering" in tool_names


@pytest.mark.contract
def test_mcp_mark_supply_recovering_tool_succeeds_for_unavailable_supply() -> None:
    """Single-source guard: only Unavailable -> Recovering; seed via
    register -> mark_unavailable so the supply lands in Unavailable
    before the test's recovering call."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        supply_id = _register_supply_via_tool(client, session_headers)
        _mark_unavailable_via_tool(client, session_headers, supply_id)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "mark_supply_recovering",
                    "arguments": {
                        "supply_id": str(supply_id),
                        "reason": "beam returning",
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["supply_id"] == str(supply_id)
