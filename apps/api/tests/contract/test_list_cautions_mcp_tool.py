"""Contract tests for the `list_cautions` MCP tool."""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_list_cautions_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "list_cautions" in tool_names


@pytest.mark.contract
def test_mcp_list_cautions_tool_returns_empty_page_with_no_data() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "list_cautions", "arguments": {}},
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    sc = result["structuredContent"]
    assert sc == {"items": [], "next_cursor": None}


@pytest.mark.contract
def test_mcp_list_cautions_tool_accepts_combined_filters() -> None:
    """Multi-value severities + statuses are passed as lists per the canonical
    shape; the tool layer translates the 'all' sentinel and the ladder."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "list_cautions",
                    "arguments": {
                        "target_kind": "Asset",
                        "category": "Wear",
                        "severities": ["Caution", "Warning"],
                        "statuses": ["all"],
                        "tag": "hexapod",
                        "limit": 25,
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["items"] == []


@pytest.mark.contract
def test_mcp_list_cautions_tool_accepts_min_severity_ladder() -> None:
    """`min_severity='Caution'` is the ladder-convenience shape: the tool
    expands it to ['Caution', 'Warning'] before calling the handler.
    Cannot be combined with explicit `severity`."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "list_cautions",
                    "arguments": {"min_severity": "Caution"},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_list_cautions_tool_iserror_on_severity_and_min_severity_together() -> None:
    """Conflict guard mirrors the REST 422; the old SQL silently returned
    the empty intersection on conflicting inputs."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "list_cautions",
                    "arguments": {
                        "severities": ["Caution"],
                        "min_severity": "Warning",
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_list_cautions_tool_iserror_on_unknown_category() -> None:
    """`Cosmic` is NOT in the CautionCategoryFilter Literal."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "list_cautions",
                    "arguments": {"category": "Cosmic"},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
