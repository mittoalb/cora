"""Contract tests for the `register_asset` MCP tool.

Shared MCP helpers live in `tests/contract/_mcp_helpers.py`.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_register_asset_tool() -> None:
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
    assert "register_asset" in tool_names


@pytest.mark.contract
def test_mcp_register_asset_tool_returns_structured_asset_id_for_enterprise_root() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {
                        "name": "ANL",
                        "level": "Enterprise",
                        "parent_id": None,
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert "asset_id" in result["structuredContent"]
    UUID(result["structuredContent"]["asset_id"])  # parses


@pytest.mark.contract
def test_mcp_register_asset_tool_returns_structured_asset_id_for_site_with_parent() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {
                        "name": "APS",
                        "level": "Site",
                        "parent_id": str(uuid4()),
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_register_asset_tool_returns_iserror_on_invalid_name() -> None:
    """Whitespace-only name passes Pydantic min_length=1 but trips
    the domain VO; FastMCP wraps the raised InvalidAssetNameError as
    isError: true with a text diagnostic."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {
                        "name": "   ",
                        "level": "Site",
                        "parent_id": str(uuid4()),
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Asset name" in result["content"][0]["text"]


@pytest.mark.contract
def test_mcp_register_asset_tool_returns_iserror_on_hierarchy_violation() -> None:
    """Enterprise with non-null parent → InvalidAssetParentError →
    FastMCP isError. Same shape as the REST 400 response."""
    parent_id = str(uuid4())
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {
                        "name": "Federated",
                        "level": "Enterprise",
                        "parent_id": parent_id,
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "Enterprise" in result["content"][0]["text"]


@pytest.mark.contract
def test_mcp_register_asset_tool_rejects_unknown_level() -> None:
    """FastMCP's argument schema enforces the StrEnum vocabulary;
    unknown levels surface as isError before the handler runs."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {
                        "name": "X",
                        "level": "Beamline",
                        "parent_id": str(uuid4()),
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_register_asset_tool_rejects_missing_arguments() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {
                    "name": "register_asset",
                    "arguments": {},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
