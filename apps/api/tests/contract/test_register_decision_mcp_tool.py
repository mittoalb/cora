"""Contract tests for the `register_decision` and `get_decision` MCP tools."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_actor(client: TestClient) -> str:
    return client.post("/actors", json={"name": "Test Operator"}).json()["actor_id"]


@pytest.mark.contract
def test_mcp_lists_decision_tools() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "register_decision" in tool_names
    assert "get_decision" in tool_names


@pytest.mark.contract
def test_mcp_register_decision_tool_succeeds_minimal() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "register_decision",
                    "arguments": {
                        "actor_id": actor_id,
                        "context": "RecipeApproval",
                        "choice": "Approved",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_register_decision_tool_with_full_audit_metadata() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "register_decision",
                    "arguments": {
                        "actor_id": actor_id,
                        "context": "ProcedureExecution",
                        "choice": "Pass",
                        "decision_rule": "iso17025:7.1.3:simple_acceptance",
                        "reasoning": "Within tolerance.",
                        "confidence": 0.95,
                        "confidence_source": "ensemble",
                        "alternatives": ["Pass", "Fail", "Re-measure"],
                        "decision_inputs": {"measured": 1.2, "limit": 1.5},
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_register_decision_tool_returns_iserror_for_missing_actor() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "register_decision",
                    "arguments": {
                        "actor_id": str(uuid4()),
                        "context": "RecipeApproval",
                        "choice": "Approved",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "actor_id" in body["result"]["content"][0]["text"]


@pytest.mark.contract
def test_mcp_get_decision_tool_returns_decision_after_registration() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        decision_id = client.post(
            "/decisions",
            json={"actor_id": actor_id, "context": "RecipeApproval", "choice": "Approved"},
        ).json()["decision_id"]
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "get_decision",
                    "arguments": {"decision_id": decision_id},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    structured = body["result"]["structuredContent"]
    assert structured["id"] == decision_id
    assert structured["choice"] == "Approved"


@pytest.mark.contract
def test_mcp_get_decision_tool_returns_iserror_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {
                    "name": "get_decision",
                    "arguments": {"decision_id": str(uuid4())},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
