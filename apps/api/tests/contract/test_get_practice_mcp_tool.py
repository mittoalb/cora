"""Contract tests for the `get_practice` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_practice_via_tool(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "APS Standard Tomography",
    method_id: str | None = None,
    site_id: str | None = None,
) -> tuple[UUID, str, str]:
    method_id = method_id or str(uuid4())
    site_id = site_id or str(uuid4())
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "define_practice",
                "arguments": {
                    "name": name,
                    "method_id": method_id,
                    "site_id": site_id,
                },
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return (
        UUID(body["result"]["structuredContent"]["practice_id"]),
        method_id,
        site_id,
    )


@pytest.mark.contract
def test_mcp_lists_get_practice_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "get_practice" in tool_names


@pytest.mark.contract
def test_mcp_get_practice_tool_returns_structured_practice_for_known_id() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        practice_id, method_id, site_id = _define_practice_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_practice",
                    "arguments": {"practice_id": str(practice_id)},
                },
            },
            headers=headers,
        )

    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert structured["id"] == str(practice_id)
    assert structured["name"] == "APS Standard Tomography"
    assert structured["method_id"] == method_id
    assert structured["site_id"] == site_id
    assert structured["status"] == "Defined"
    assert structured["version"] is None


@pytest.mark.contract
def test_mcp_get_practice_tool_returns_iserror_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_practice",
                    "arguments": {"practice_id": str(uuid4())},
                },
            },
            headers=headers,
        )

    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
