"""Contract tests for the `supersede_caution` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_args(asset_id: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "target": {"kind": "Asset", "id": asset_id},
        "category": "Wear",
        "severity": "Caution",
        "text": "original text",
        "workaround": "original workaround",
    }
    base.update(overrides)
    return base


def _supersede_args(parent_id: str, asset_id: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "parent_caution_id": parent_id,
        "target": {"kind": "Asset", "id": asset_id},
        "category": "Wear",
        "severity": "Caution",
        "text": "amended text",
        "workaround": "amended workaround",
    }
    base.update(overrides)
    return base


def _seed_parent_via_mcp(
    client: TestClient,
    session_headers: dict[str, str],
    asset_id: str,
) -> str:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {"name": "register_caution", "arguments": _register_args(asset_id)},
        },
        headers=session_headers,
    )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False, body
    return str(body["result"]["structuredContent"]["caution_id"])


@pytest.mark.contract
def test_mcp_lists_supersede_caution_tool() -> None:
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
    assert "supersede_caution" in tool_names


@pytest.mark.contract
def test_mcp_supersede_caution_tool_returns_structured_child_caution_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        asset_id = str(uuid4())
        parent_id = _seed_parent_via_mcp(client, session_headers, asset_id)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "supersede_caution",
                    "arguments": _supersede_args(parent_id, asset_id),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert "caution_id" in result["structuredContent"]
    child_id = result["structuredContent"]["caution_id"]
    UUID(child_id)
    assert child_id != parent_id


@pytest.mark.contract
def test_mcp_supersede_caution_tool_returns_iserror_on_blank_workaround() -> None:
    """Whitespace-only workaround trips the VO; FastMCP wraps as isError."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        asset_id = str(uuid4())
        parent_id = _seed_parent_via_mcp(client, session_headers, asset_id)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "supersede_caution",
                    "arguments": _supersede_args(parent_id, asset_id, workaround="   "),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Caution workaround" in result["content"][0]["text"]
