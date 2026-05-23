"""Contract tests for the `dismount_subject` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_subject_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "register_subject",
                "arguments": {"name": "Sample-A1"},
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["subject_id"])


@pytest.mark.contract
def test_mcp_lists_dismount_subject_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "dismount_subject" in tool_names


@pytest.mark.contract
def test_mcp_dismount_subject_tool_returns_iserror_for_unknown_subject() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "dismount_subject",
                    "arguments": {"subject_id": str(uuid4()), "reason": "x"},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_dismount_subject_tool_returns_iserror_when_subject_only_received() -> None:
    """Subject not currently mounted -> SubjectCannotDismountError -> isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        subject_id = _register_subject_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "dismount_subject",
                    "arguments": {"subject_id": str(subject_id), "reason": "x"},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
