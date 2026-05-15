"""Contract tests for the `restore_supply` MCP tool (10a-b)."""

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
                    "name": "35-BM LN2",
                },
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["supply_id"])


def _call_tool(
    client: TestClient,
    headers: dict[str, str],
    *,
    request_id: int,
    name: str,
    supply_id: UUID,
    reason: str,
) -> None:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": {"supply_id": str(supply_id), "reason": reason},
            },
        },
        headers=headers,
    )
    assert parse_sse_data(response.text)["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_lists_restore_supply_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "restore_supply" in tool_names


@pytest.mark.contract
def test_mcp_restore_supply_tool_succeeds_for_recovering_supply() -> None:
    """Single-source guard: only Recovering -> Available; seed the supply
    through register -> mark_available -> mark_unavailable -> mark_recovering
    so it lands in Recovering before the test's restore call."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        supply_id = _register_supply_via_tool(client, session_headers)
        _call_tool(
            client,
            session_headers,
            request_id=101,
            name="mark_supply_available",
            supply_id=supply_id,
            reason="walkdown",
        )
        _call_tool(
            client,
            session_headers,
            request_id=102,
            name="mark_supply_unavailable",
            supply_id=supply_id,
            reason="beam dump",
        )
        _call_tool(
            client,
            session_headers,
            request_id=103,
            name="mark_supply_recovering",
            supply_id=supply_id,
            reason="beam returning",
        )
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "restore_supply",
                    "arguments": {
                        "supply_id": str(supply_id),
                        "reason": "ops confirms stable",
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["supply_id"] == str(supply_id)
