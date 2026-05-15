"""Contract tests for the `register_supply` MCP tool."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_register_supply_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "register_supply" in tool_names


@pytest.mark.contract
def test_mcp_register_supply_tool_returns_structured_supply_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
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
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert "supply_id" in result["structuredContent"]
    UUID(result["structuredContent"]["supply_id"])


@pytest.mark.contract
def test_mcp_register_supply_tool_returns_iserror_on_whitespace_name() -> None:
    """Whitespace-only name passes Pydantic min_length=1 but trips the
    SupplyName VO; FastMCP wraps the raised InvalidSupplyNameError as
    isError: true with a text diagnostic."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "register_supply",
                    "arguments": {
                        "scope": "Beamline",
                        "kind": "LiquidNitrogen",
                        "name": "   ",
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Supply name" in result["content"][0]["text"]


@pytest.mark.contract
def test_mcp_register_supply_tool_rejects_missing_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "register_supply",
                    "arguments": {"scope": "Beamline"},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


# Known gap: SupplyAlreadyExists -> isError on the MCP wire is verified
# only at the REST layer (see test_register_supply_endpoint.py
# ::test_post_supplies_returns_409_when_handler_raises_already_exists).
# MCP can't intercept handlers via FastAPI dependency_overrides because
# the MCP tool closure reads `app.state.supply.register_supply` directly,
# bypassing the route's `_get_handler` dependency. Patching app.state
# requires either pre-lifespan injection (overwritten by lifespan) or
# mutating the frozen SupplyHandlers dataclass mid-test (brittle). Since
# UUIDv7 makes the AlreadyExists path nearly impossible in production,
# the REST coverage of the defensive guard is sufficient.
