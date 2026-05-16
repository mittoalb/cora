"""Contract tests for the `register_campaign` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _args(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "test",
        "intent": "InSitu",
        "lead_actor_id": str(uuid4()),
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_mcp_lists_register_campaign_tool() -> None:
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
    assert "register_campaign" in tool_names


@pytest.mark.contract
def test_mcp_register_campaign_tool_returns_structured_campaign_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "register_campaign", "arguments": _args()},
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert "campaign_id" in result["structuredContent"]
    UUID(result["structuredContent"]["campaign_id"])


@pytest.mark.contract
def test_mcp_register_campaign_tool_returns_iserror_on_whitespace_name() -> None:
    """Whitespace-only name passes Pydantic min_length=1 but trips the VO."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "register_campaign",
                    "arguments": _args(name="   "),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Campaign name" in result["content"][0]["text"]
