"""Contract tests for the `get_procedure` MCP tool."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_procedure(client: TestClient) -> str:
    response = client.post("/procedures", json={"name": "Vessel-A bakeout", "kind": "bakeout"})
    assert response.status_code == 201, response.text
    return response.json()["procedure_id"]


@pytest.mark.contract
def test_mcp_lists_get_procedure_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "get_procedure" in tool_names


@pytest.mark.contract
def test_mcp_get_procedure_tool_returns_procedure_on_hit() -> None:
    with TestClient(create_app()) as client:
        procedure_id = _register_procedure(client)
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_procedure",
                    "arguments": {"procedure_id": procedure_id},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    output = body["result"]["structuredContent"]
    assert output["id"] == procedure_id
    assert output["name"] == "Vessel-A bakeout"
    assert output["kind"] == "bakeout"
    assert output["status"] == "Defined"


@pytest.mark.contract
def test_mcp_get_procedure_tool_returns_iserror_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "get_procedure",
                    "arguments": {"procedure_id": str(uuid4())},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
