"""Contract tests for the `get_clearance` MCP tool."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _seed_clearance(client: TestClient, session_headers: dict[str, str]) -> str:
    """Create a clearance via the MCP register tool, return its id."""
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {
                "name": "register_clearance",
                "arguments": {
                    "kind": "ESAF",
                    "facility_asset_id": str(uuid4()),
                    "title": "Pilot",
                    "bindings": [{"kind": "Run", "id": str(uuid4())}],
                    "risk_band": "Yellow",
                },
            },
        },
        headers=session_headers,
    )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    return str(body["result"]["structuredContent"]["clearance_id"])


@pytest.mark.contract
def test_mcp_lists_get_clearance_tool() -> None:
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
    assert "get_clearance" in tool_names


@pytest.mark.contract
def test_mcp_get_clearance_tool_returns_structured_state_on_hit() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        cid = _seed_clearance(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_clearance",
                    "arguments": {"clearance_id": cid},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["id"] == cid
    assert structured["kind"] == "ESAF"
    assert structured["status"] == "Defined"
    assert structured["risk_band"] == "Yellow"


@pytest.mark.contract
def test_mcp_get_clearance_tool_returns_iserror_on_miss() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_clearance",
                    "arguments": {"clearance_id": str(uuid4())},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
