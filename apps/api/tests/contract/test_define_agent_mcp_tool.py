"""Contract tests for the `define_agent` MCP tool."""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _args(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "kind": "RunDebriefer",
        "name": "Run Debrief",
        "version": "v1",
        "model_ref": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "snapshot_pin": None,
        },
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_mcp_lists_define_agent_tool() -> None:
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
    assert "define_agent" in tool_names


@pytest.mark.contract
def test_mcp_define_agent_returns_structured_agent_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "define_agent", "arguments": _args()},
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert "agent_id" in result["structuredContent"]
    UUID(result["structuredContent"]["agent_id"])


@pytest.mark.contract
def test_mcp_define_agent_returns_iserror_on_invalid_https() -> None:
    """http:// canonical_uri trips the domain VO; FastMCP wraps the
    raised InvalidAgentCanonicalURIError as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "define_agent",
                    "arguments": _args(canonical_uri="http://no-https.example.org"),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_define_agent_returns_iserror_on_empty_kind() -> None:
    """Pydantic min_length=1 boundary trips on empty kind; FastMCP
    surfaces the validation error as isError: true. Closes gate-review
    contract-symmetry P1-2 (MCP side had only one isError test vs
    REST's five 4xx assertions)."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "define_agent", "arguments": _args(kind="")},
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_define_agent_returns_iserror_on_over_cap_capabilities() -> None:
    """Over-cap capabilities trips the domain VO; FastMCP surfaces
    InvalidAgentCapabilitiesError as isError: true."""
    over_cap = [f"cap-{i}" for i in range(33)]  # AGENT_CAPABILITIES_MAX_COUNT + 1
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "define_agent", "arguments": _args(capabilities=over_cap)},
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
