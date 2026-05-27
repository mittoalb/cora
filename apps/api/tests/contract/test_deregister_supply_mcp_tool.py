"""Contract tests for the `deregister_supply` MCP tool."""

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


@pytest.mark.contract
def test_mcp_lists_deregister_supply_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "deregister_supply" in tool_names


@pytest.mark.contract
def test_mcp_deregister_supply_tool_succeeds_from_unknown() -> None:
    """`deregister_supply` accepts any non-Decommissioned status; pin the
    Unknown case (no intervening transitions)."""
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
                    "name": "deregister_supply",
                    "arguments": {
                        "supply_id": str(supply_id),
                        "reason": "typo at registration",
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["supply_id"] == str(supply_id)


@pytest.mark.contract
def test_mcp_deregister_supply_tool_is_strict_not_idempotent() -> None:
    """Re-deregister returns an MCP error (mapped from SupplyCannotDeregisterError)."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        supply_id = _register_supply_via_tool(client, session_headers)
        first = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "deregister_supply",
                    "arguments": {"supply_id": str(supply_id), "reason": "first"},
                },
            },
            headers=session_headers,
        )
        assert parse_sse_data(first.text)["result"]["isError"] is False
        second = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "deregister_supply",
                    "arguments": {"supply_id": str(supply_id), "reason": "second"},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(second.text)
    assert body["result"]["isError"] is True
