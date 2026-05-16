"""Contract tests for the `register_caution` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _args(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "target": {"kind": "Asset", "id": str(uuid4())},
        "category": "Wear",
        "severity": "Caution",
        "text": "hexapod stalls below 0.5 mm/s",
        "workaround": "run at 0.6 mm/s",
        "author_actor_id": str(uuid4()),
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_mcp_lists_register_caution_tool() -> None:
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
    assert "register_caution" in tool_names


@pytest.mark.contract
def test_mcp_register_caution_tool_returns_structured_caution_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "register_caution", "arguments": _args()},
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert "caution_id" in result["structuredContent"]
    UUID(result["structuredContent"]["caution_id"])


@pytest.mark.contract
def test_mcp_register_caution_tool_returns_iserror_on_whitespace_workaround() -> None:
    """Whitespace-only workaround passes Pydantic min_length=1 but trips the VO;
    FastMCP wraps the raised InvalidCautionWorkaroundError as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "register_caution",
                    "arguments": _args(workaround="   "),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Caution workaround" in result["content"][0]["text"]


@pytest.mark.contract
def test_mcp_register_caution_tool_rejects_missing_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "register_caution",
                    "arguments": {"category": "Wear"},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
