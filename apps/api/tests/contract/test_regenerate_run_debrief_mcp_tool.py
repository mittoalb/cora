"""Contract tests for the `regenerate_run_debrief` MCP tool."""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_regenerate_run_debrief_tool() -> None:
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
    assert "regenerate_run_debrief" in tool_names


@pytest.mark.contract
def test_mcp_regenerate_run_debrief_tool_advertises_signature() -> None:
    """Tool schema must declare `run_id` (required UUID) +
    `parent_decision_id` (optional UUID). The MCP description should
    mention `RunDebrief` so an LLM/agent caller can find it."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool = next(t for t in body["result"]["tools"] if t["name"] == "regenerate_run_debrief")
    assert "RunDebrief" in tool["description"]
    properties = tool["inputSchema"]["properties"]
    assert "run_id" in properties
    assert "parent_decision_id" in properties
    required = tool["inputSchema"].get("required", [])
    assert "run_id" in required
    assert "parent_decision_id" not in required


@pytest.mark.contract
def test_mcp_regenerate_run_debrief_returns_iserror_when_llm_unwired() -> None:
    """Default app_env=test wires `kernel.llm=None`; the tool's
    get_handler() raises RuntimeError, which the MCP framework
    surfaces as `isError=true`. Mirrors the REST 503 semantics."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "regenerate_run_debrief",
                    "arguments": {"run_id": "01900000-0000-7000-8000-000000000001"},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True, result
