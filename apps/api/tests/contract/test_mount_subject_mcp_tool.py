"""Contract tests for the `mount_subject` MCP tool.

Shared MCP helpers live in `tests/contract/_mcp_helpers.py`.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data
from tests.contract._subject_helpers import register_active_asset


def _register_subject_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    """Helper: register via MCP tool and return the new subject's id."""
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "register_subject",
                "arguments": {"name": "Sample-A1"},
            },
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["subject_id"])


@pytest.mark.contract
def test_mcp_lists_mount_subject_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "mount_subject" in tool_names


@pytest.mark.contract
def test_mcp_mount_subject_tool_succeeds_for_received_subject() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        subject_id = _register_subject_via_tool(client, headers)
        asset_id = register_active_asset(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "mount_subject",
                    "arguments": {"subject_id": str(subject_id), "asset_id": asset_id},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_mount_subject_tool_returns_iserror_for_unknown_subject() -> None:
    """SubjectNotFoundError propagates → FastMCP wraps as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        asset_id = register_active_asset(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "mount_subject",
                    "arguments": {"subject_id": str(uuid4()), "asset_id": asset_id},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_mount_subject_tool_returns_iserror_when_already_mounted() -> None:
    """SubjectCannotMountError propagates → FastMCP wraps as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        subject_id = _register_subject_via_tool(client, headers)
        asset_id = register_active_asset(client)

        # First mount: success.
        first = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "mount_subject",
                    "arguments": {"subject_id": str(subject_id), "asset_id": asset_id},
                },
            },
            headers=headers,
        )
        assert parse_sse_data(first.text)["result"]["isError"] is False

        # Second mount: isError.
        second = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "mount_subject",
                    "arguments": {"subject_id": str(subject_id), "asset_id": asset_id},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(second.text)
    assert body["result"]["isError"] is True
    text = body["result"]["content"][0]["text"]
    assert "Mounted" in text
    assert "Received" in text
