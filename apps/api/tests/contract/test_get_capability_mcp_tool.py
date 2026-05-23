"""Contract tests for the `get_capability` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_capability_via_tool(
    client: TestClient,
    session_headers: dict[str, str],
    code: str = "cora.capability.x",
    required_affordances: list[str] | None = None,
) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "define_capability",
                "arguments": {
                    "code": code,
                    "name": code.rsplit(".", 1)[-1],
                    "required_affordances": required_affordances or [],
                    "executor_shapes": ["Method"],
                },
            },
        },
        headers=session_headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["capability_id"])


@pytest.mark.contract
def test_mcp_lists_get_capability_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "get_capability" in tool_names


@pytest.mark.contract
def test_mcp_get_capability_returns_structured_capability_on_hit() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        cap_id = _define_capability_via_tool(
            client,
            session_headers,
            code="cora.capability.tomo",
            required_affordances=["Rotatable", "Triggerable"],
        )
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_capability",
                    "arguments": {"capability_id": str(cap_id)},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    sc = body["result"]["structuredContent"]
    assert sc["id"] == str(cap_id)
    assert sc["code"] == "cora.capability.tomo"
    assert sc["status"] == "Defined"
    # Sorted alphabetically per response-determinism lock.
    assert sc["required_affordances"] == ["Rotatable", "Triggerable"]


@pytest.mark.contract
def test_mcp_get_capability_returns_iserror_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "get_capability",
                    "arguments": {"capability_id": str(uuid4())},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
