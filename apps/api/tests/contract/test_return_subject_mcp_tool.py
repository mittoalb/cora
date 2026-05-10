"""Contract tests for the `return_subject` MCP tool.

Mirrors the prior subject MCP contract tests. Walks the subject through
the lifecycle (register + mount + remove) before exercising the
terminal return tool.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _call_tool(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str,
    args: dict[str, str],
    request_id: int,
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        },
        headers=headers,
    )
    assert response.status_code == 200
    return parse_sse_data(response.text)


def _register_mount_remove_via_tools(client: TestClient, headers: dict[str, str]) -> UUID:
    """Helper: walk a subject to Removed via MCP tools, return its id."""
    body = _call_tool(
        client,
        headers,
        name="register_subject",
        args={"name": "Sample-A1"},
        request_id=2,
    )
    subject_id = UUID(body["result"]["structuredContent"]["subject_id"])
    body = _call_tool(
        client,
        headers,
        name="mount_subject",
        args={"subject_id": str(subject_id)},
        request_id=3,
    )
    assert body["result"]["isError"] is False
    body = _call_tool(
        client,
        headers,
        name="remove_subject",
        args={"subject_id": str(subject_id)},
        request_id=4,
    )
    assert body["result"]["isError"] is False
    return subject_id


@pytest.mark.contract
def test_mcp_lists_return_subject_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "return_subject" in tool_names


@pytest.mark.contract
def test_mcp_return_subject_tool_succeeds_for_removed_subject() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        subject_id = _register_mount_remove_via_tools(client, headers)
        body = _call_tool(
            client,
            headers,
            name="return_subject",
            args={"subject_id": str(subject_id)},
            request_id=5,
        )
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_return_subject_tool_returns_iserror_for_unknown_subject() -> None:
    """SubjectNotFoundError propagates -> FastMCP wraps as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers,
            name="return_subject",
            args={"subject_id": str(uuid4())},
            request_id=6,
        )
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_return_subject_tool_returns_iserror_when_not_yet_removed() -> None:
    """SubjectCannotReturnError on Mounted subject -> isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers,
            name="register_subject",
            args={"name": "Sample-A1"},
            request_id=7,
        )
        subject_id = UUID(body["result"]["structuredContent"]["subject_id"])
        body = _call_tool(
            client,
            headers,
            name="mount_subject",
            args={"subject_id": str(subject_id)},
            request_id=8,
        )
        assert body["result"]["isError"] is False
        body = _call_tool(
            client,
            headers,
            name="return_subject",
            args={"subject_id": str(subject_id)},
            request_id=9,
        )
    assert body["result"]["isError"] is True
    text = body["result"]["content"][0]["text"]
    assert "Mounted" in text
    assert "Removed" in text
