"""Contract tests for the `get_caution` MCP tool."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_args(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "target": {"kind": "Asset", "id": str(uuid4())},
        "category": "Wear",
        "severity": "Caution",
        "text": "look me up",
        "workaround": "run at lower speed",
    }
    base.update(overrides)
    return base


def _seed_via_mcp(client: TestClient, session_headers: dict[str, str]) -> str:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {"name": "register_caution", "arguments": _register_args()},
        },
        headers=session_headers,
    )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False, body
    return str(body["result"]["structuredContent"]["caution_id"])


@pytest.mark.contract
def test_mcp_lists_get_caution_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "get_caution" in tool_names


@pytest.mark.contract
def test_mcp_get_caution_tool_returns_structured_caution_on_hit() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        caution_id = _seed_via_mcp(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_caution",
                    "arguments": {"caution_id": caution_id},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    sc = result["structuredContent"]
    assert sc["id"] == caution_id
    assert sc["status"] == "Active"
    assert sc["category"] == "Wear"
    assert sc["severity"] == "Caution"


@pytest.mark.contract
def test_mcp_get_caution_tool_returns_iserror_on_miss() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_caution",
                    "arguments": {"caution_id": str(uuid4())},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "not found" in result["content"][0]["text"].lower()
