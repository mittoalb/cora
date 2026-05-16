"""Contract tests for the `get_campaign` MCP tool."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _seed_via_rest(client: TestClient) -> str:
    response = client.post(
        "/campaigns",
        json={
            "name": "test",
            "intent": "InSitu",
            "lead_actor_id": str(uuid4()),
        },
    )
    assert response.status_code == 201
    return str(response.json()["campaign_id"])


@pytest.mark.contract
def test_mcp_lists_get_campaign_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "get_campaign" in tool_names


@pytest.mark.contract
def test_mcp_get_campaign_tool_returns_structured_payload_on_hit() -> None:
    with TestClient(create_app()) as client:
        cid = _seed_via_rest(client)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_campaign",
                    "arguments": {"campaign_id": cid},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["id"] == cid
    assert result["structuredContent"]["status"] == "Planned"


@pytest.mark.contract
def test_mcp_get_campaign_tool_returns_iserror_on_miss() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_campaign",
                    "arguments": {"campaign_id": str(uuid4())},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
