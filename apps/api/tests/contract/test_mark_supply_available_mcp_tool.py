"""Contract tests for the `mark_supply_available` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_supply_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    """Seed a supply via the MCP tool (not REST) so the contract test
    exercises the full MCP write surface. Mirrors capability's
    `_define_family_via_tool` pattern."""
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
                },
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["supply_id"])


@pytest.mark.contract
def test_mcp_lists_mark_supply_available_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "mark_supply_available" in tool_names


@pytest.mark.contract
def test_mcp_mark_supply_available_tool_succeeds_for_unknown_supply() -> None:
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
                    "name": "mark_supply_available",
                    "arguments": {
                        "supply_id": str(supply_id),
                        "reason": "operator walkdown",
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
def test_mcp_mark_supply_available_tool_iserror_on_unknown_supply_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "mark_supply_available",
                    "arguments": {"supply_id": str(uuid4()), "reason": "r"},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "not found" in result["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_mark_supply_available_tool_iserror_on_re_marking() -> None:
    """Strict-not-idempotent: second call against same supply raises 409 / isError."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        supply_id = _register_supply_via_tool(client, session_headers)
        for call_id in (3, 4):
            response = client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": call_id,
                    "method": "tools/call",
                    "params": {
                        "name": "mark_supply_available",
                        "arguments": {
                            "supply_id": str(supply_id),
                            "reason": f"call-{call_id}",
                        },
                    },
                },
                headers=session_headers,
            )
            body = parse_sse_data(response.text)
            if call_id == 3:
                assert body["result"]["isError"] is False
            else:
                assert body["result"]["isError"] is True
                assert "cannot be marked available" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_mark_supply_available_tool_iserror_on_whitespace_reason() -> None:
    """Whitespace-only reason passes Pydantic min_length=1 but trips the
    SupplyReason VO at the decider; FastMCP wraps the raised
    InvalidSupplyReasonError as isError: true with a text diagnostic."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        supply_id = _register_supply_via_tool(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "mark_supply_available",
                    "arguments": {"supply_id": str(supply_id), "reason": "   "},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Supply transition reason" in result["content"][0]["text"]
