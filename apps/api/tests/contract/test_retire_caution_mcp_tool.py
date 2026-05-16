"""Contract tests for the `retire_caution` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_args(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "target": {"kind": "Asset", "id": str(uuid4())},
        "category": "Wear",
        "severity": "Caution",
        "text": "to be retired",
        "workaround": "no longer applies",
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
def test_mcp_lists_retire_caution_tool() -> None:
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
    assert "retire_caution" in tool_names


@pytest.mark.contract
def test_mcp_retire_caution_tool_returns_structured_caution_id() -> None:
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
                    "name": "retire_caution",
                    "arguments": {"caution_id": caution_id, "reason": "Resolved"},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["caution_id"] == caution_id
    UUID(result["structuredContent"]["caution_id"])


@pytest.mark.contract
def test_mcp_retire_caution_tool_returns_iserror_when_not_found() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "retire_caution",
                    "arguments": {"caution_id": str(uuid4()), "reason": "Resolved"},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
