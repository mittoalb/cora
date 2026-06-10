"""Contract tests for the `register_clearance` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_register_clearance_tool() -> None:
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
    assert "register_clearance" in tool_names


@pytest.mark.contract
def test_mcp_register_clearance_tool_returns_structured_clearance_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "register_clearance",
                    "arguments": {
                        "kind": "ESAF",
                        "facility_code": "cora",
                        "title": "Pilot ESAF",
                        "bindings": [{"kind": "Run", "id": str(uuid4())}],
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert "clearance_id" in result["structuredContent"]
    UUID(result["structuredContent"]["clearance_id"])


@pytest.mark.contract
def test_mcp_register_clearance_tool_accepts_multi_binding() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "register_clearance",
                    "arguments": {
                        "kind": "SAF",
                        "facility_code": "cora",
                        "title": "Multi-bind",
                        "bindings": [
                            {"kind": "Subject", "id": str(uuid4())},
                            {"kind": "Asset", "id": str(uuid4())},
                            {"kind": "External", "scheme": "proposal", "value": "GUP-1"},
                        ],
                        "risk_band": "Yellow",
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_register_clearance_tool_returns_iserror_on_whitespace_title() -> None:
    """Whitespace-only title passes Pydantic min_length=1 but trips the VO;
    FastMCP wraps the raised InvalidClearanceTitleError as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "register_clearance",
                    "arguments": {
                        "kind": "ESAF",
                        "facility_code": "cora",
                        "title": "   ",
                        "bindings": [{"kind": "Run", "id": str(uuid4())}],
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
