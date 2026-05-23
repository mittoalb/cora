"""Contract tests for the `define_capability` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_define_capability_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "define_capability" in tool_names


@pytest.mark.contract
def test_mcp_define_capability_tool_returns_structured_capability_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "define_capability",
                    "arguments": {
                        "code": "cora.capability.flyscan",
                        "name": "FlyScan Tomography",
                        "required_affordances": ["Rotatable", "Triggerable"],
                        "executor_shapes": ["Method"],
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert "capability_id" in result["structuredContent"]
    UUID(result["structuredContent"]["capability_id"])


@pytest.mark.contract
def test_mcp_define_capability_rejects_missing_namespace() -> None:
    """Pydantic validation at MCP boundary rejects unnamespaced code → isError."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "define_capability",
                    "arguments": {
                        "code": "flyscan",
                        "name": "FlyScan",
                        "required_affordances": [],
                        "executor_shapes": ["Method"],
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_define_capability_rejects_unknown_affordance_string() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "define_capability",
                    "arguments": {
                        "code": "cora.capability.x",
                        "name": "X",
                        "required_affordances": ["NotARealAffordance"],
                        "executor_shapes": ["Method"],
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_define_capability_dedupes_via_frozenset() -> None:
    """Duplicate affordances in the request dedupe at the handler boundary."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "define_capability",
                    "arguments": {
                        "code": "cora.capability.dup",
                        "name": "Dup",
                        "required_affordances": [
                            "Rotatable",
                            "Rotatable",
                            "Homeable",
                        ],
                        "executor_shapes": ["Method"],
                    },
                },
            },
            headers=session_headers,
        )
        capability_id = parse_sse_data(response.text)["result"]["structuredContent"][
            "capability_id"
        ]
        get = client.get(f"/capabilities/{capability_id}")
    body = get.json()
    assert body["required_affordances"] == ["Homeable", "Rotatable"]


# Unused import guard for pytest's discovery; uuid4 imported for parity with siblings.
_ = uuid4
