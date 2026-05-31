"""Contract tests for the `append_reasoning_entries` MCP tool."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _seed_decision(client: TestClient) -> str:
    actor_id = client.post("/actors", json={"name": "Test Actor"}).json()["actor_id"]
    return client.post(
        "/decisions",
        json={"actor_id": actor_id, "context": "RecipeApproval", "choice": "Approved"},
    ).json()["decision_id"]


@pytest.mark.contract
def test_mcp_lists_append_reasoning_entries_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "append_reasoning_entries" in tool_names


@pytest.mark.contract
def test_mcp_append_reasoning_entries_tool_succeeds_on_minimum_args() -> None:
    with TestClient(create_app()) as client:
        decision_id = _seed_decision(client)
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "append_reasoning_entries",
                    "arguments": {
                        "decision_id": decision_id,
                        "event_id": str(uuid4()),
                        "occurred_at": "2026-05-12T12:00:00+00:00",
                        "operation_name": "chat",
                        "provider_name": "anthropic",
                        "request_model": "claude-opus-4-7",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    assert body["result"]["structuredContent"]["event_count"] == 1


@pytest.mark.contract
def test_mcp_append_reasoning_entries_tool_returns_iserror_for_unknown_decision() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "append_reasoning_entries",
                    "arguments": {
                        "decision_id": str(uuid4()),
                        "event_id": str(uuid4()),
                        "occurred_at": "2026-05-12T12:00:00+00:00",
                        "operation_name": "chat",
                        "provider_name": "anthropic",
                        "request_model": "claude-opus-4-7",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
