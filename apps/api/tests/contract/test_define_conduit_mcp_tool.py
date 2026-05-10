"""Contract tests for the `define_conduit` MCP tool.

Mirror of `test_define_zone_mcp_tool.py`. Shared MCP helpers live in
`tests/contract/_mcp_helpers.py`.
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_SOURCE = "01900000-0000-7000-8000-00000000aaaa"
_TARGET = "01900000-0000-7000-8000-00000000bbbb"


@pytest.mark.contract
def test_mcp_lists_define_conduit_tool() -> None:
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
    assert "define_conduit" in tool_names


@pytest.mark.contract
def test_mcp_define_conduit_tool_returns_structured_conduit_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "define_conduit",
                    "arguments": {
                        "name": "Detector-to-Storage",
                        "source_zone_id": _SOURCE,
                        "target_zone_id": _TARGET,
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert "conduit_id" in result["structuredContent"]
    UUID(result["structuredContent"]["conduit_id"])  # parses without raising


@pytest.mark.contract
def test_mcp_define_conduit_tool_returns_iserror_on_invalid_input() -> None:
    """Whitespace-only name passes Pydantic min_length=1 but trips the
    domain VO; FastMCP wraps the raised InvalidConduitNameError as
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
                    "name": "define_conduit",
                    "arguments": {
                        "name": "   ",
                        "source_zone_id": _SOURCE,
                        "target_zone_id": _TARGET,
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Conduit name" in result["content"][0]["text"]


@pytest.mark.contract
def test_mcp_define_conduit_tool_rejects_missing_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "define_conduit",
                    "arguments": {"name": "Detector-to-Storage"},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
