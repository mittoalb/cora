"""Contract tests for the `get_agent` MCP tool (Phase 8f-a)."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_args() -> dict[str, object]:
    return {
        "kind": "RunDebrief",
        "name": "Run Debrief",
        "version": "v1",
        "model_ref": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "snapshot_pin": None,
        },
    }


@pytest.mark.contract
def test_mcp_lists_get_agent_tool() -> None:
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
    assert "get_agent" in tool_names


@pytest.mark.contract
def test_mcp_get_agent_returns_structured_agent_on_hit() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        define_resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "define_agent", "arguments": _define_args()},
            },
            headers=session_headers,
        )
        agent_id = parse_sse_data(define_resp.text)["result"]["structuredContent"]["agent_id"]
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "get_agent", "arguments": {"agent_id": agent_id}},
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    sc = result["structuredContent"]
    assert sc["id"] == agent_id
    assert sc["kind"] == "RunDebrief"
    assert sc["status"] == "Defined"


@pytest.mark.contract
def test_mcp_get_agent_returns_iserror_on_unknown_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "get_agent", "arguments": {"agent_id": str(uuid4())}},
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
