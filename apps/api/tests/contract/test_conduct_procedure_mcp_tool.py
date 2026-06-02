"""Contract tests for the `conduct_procedure` MCP tool.

Mirrors the REST contract test (same wire shape + same wire-up:
in-process InMemoryControlPort + empty default ActionRegistry).
Covers tool listing, happy path (empty steps), action failure
(unknown name), and setpoint failure (unconnected address).
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_via_mcp(client: TestClient, headers: dict[str, str], *, request_id: int) -> UUID:
    reg = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": "register_procedure",
                "arguments": {"name": "Vessel-A bakeout", "kind": "bakeout"},
            },
        },
        headers=headers,
    )
    return UUID(parse_sse_data(reg.text)["result"]["structuredContent"]["procedure_id"])


@pytest.mark.contract
def test_mcp_lists_conduct_procedure_tool() -> None:
    """The Operation BC registers the conduct_procedure tool on the FastMCP server."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "conduct_procedure" in tool_names


@pytest.mark.contract
def test_mcp_conduct_procedure_empty_steps_returns_succeeded_for_registered_procedure() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        pid = _register_via_mcp(client, headers, request_id=1)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "conduct_procedure",
                    "arguments": {
                        "procedure_id": str(pid),
                        "body": {"steps": []},
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    structured: dict[str, Any] = body["result"]["structuredContent"]
    assert structured["procedure_id"] == str(pid)
    assert structured["completed_count"] == 0
    assert structured["succeeded"] is True
    assert structured["failure"] is None


@pytest.mark.contract
def test_mcp_conduct_procedure_with_unknown_action_returns_failure_in_structured_content() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        pid = _register_via_mcp(client, headers, request_id=1)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "conduct_procedure",
                    "arguments": {
                        "procedure_id": str(pid),
                        "body": {"steps": [{"kind": "action", "name": "no_such_body"}]},
                    },
                },
            },
            headers=headers,
        )
    structured: dict[str, Any] = parse_sse_data(response.text)["result"]["structuredContent"]
    assert structured["succeeded"] is False
    failure = structured["failure"]
    assert failure["source_kind"] == "action"
    assert failure["error_class"] == "UnknownActionError"


@pytest.mark.contract
def test_mcp_conduct_procedure_against_unregistered_procedure_returns_iserror() -> None:
    """conduct() re-raises ProcedureNotFoundError; FastMCP surfaces as isError.
    Earlier shape (200-with-lifecycle-failure structured content) was rejected
    by routes.py wiring: see [[project_conduct_procedure_test_contract_drift]]
    memory."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        unknown_pid = uuid4()
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "conduct_procedure",
                    "arguments": {
                        "procedure_id": str(unknown_pid),
                        "body": {"steps": []},
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert str(unknown_pid) in body["result"]["content"][0]["text"]
