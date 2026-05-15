"""Contract tests for the `start_procedure` MCP tool."""

from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_via_mcp(client: TestClient, headers: dict[str, str]) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "register_procedure",
                "arguments": {"name": "Beam-mode change to white", "kind": "beam_mode_change"},
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    return UUID(body["result"]["structuredContent"]["procedure_id"])


def _call_start(client: TestClient, headers: dict[str, str], pid: UUID) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "start_procedure", "arguments": {"procedure_id": str(pid)}},
        },
        headers=headers,
    )
    return parse_sse_data(response.text)


@pytest.mark.contract
def test_mcp_lists_start_procedure_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "start_procedure" in tool_names


@pytest.mark.contract
def test_mcp_start_procedure_tool_succeeds_for_defined() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        pid = _register_via_mcp(client, headers)
        body = _call_start(client, headers, pid)
    assert body["result"]["isError"] is False
