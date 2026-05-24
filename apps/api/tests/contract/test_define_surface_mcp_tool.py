"""Contract tests for the `define_surface` + `get_surface` MCP tools."""

from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _call_define(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "System HTTP",
    kind: str = "http",
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "define_surface",
                "arguments": {"name": name, "kind": kind},
            },
        },
        headers=headers,
    )
    assert response.status_code == 200
    return parse_sse_data(response.text)


def _call_get(
    client: TestClient,
    headers: dict[str, str],
    *,
    surface_id: str,
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "get_surface",
                "arguments": {"surface_id": surface_id},
            },
        },
        headers=headers,
    )
    assert response.status_code == 200
    return parse_sse_data(response.text)


@pytest.mark.contract
def test_mcp_lists_define_surface_and_get_surface_tools() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "define_surface" in tool_names
    assert "get_surface" in tool_names


@pytest.mark.contract
def test_mcp_define_surface_returns_id() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_define(client, headers)
    result = body["result"]
    assert result["isError"] is False
    surface_id = result["structuredContent"]["surface_id"]
    UUID(surface_id)


@pytest.mark.contract
def test_mcp_define_surface_rejects_unknown_kind() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_define(client, headers, kind="a2a")
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_get_surface_round_trip() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        defined = _call_define(client, headers, name="System MCP stdio", kind="mcp_stdio")
        surface_id = defined["result"]["structuredContent"]["surface_id"]
        got = _call_get(client, headers, surface_id=surface_id)
    output = got["result"]["structuredContent"]
    assert output["id"] == surface_id
    assert output["kind"] == "mcp_stdio"
    assert output["status"] == "Defined"


@pytest.mark.contract
def test_mcp_get_surface_returns_iserror_when_missing() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_get(client, headers, surface_id="01900000-0000-7000-8000-deadbeef0051")
    result = body["result"]
    assert result["isError"] is True
    assert "not found" in result["content"][0]["text"].lower()
