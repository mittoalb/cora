"""Contract tests for the `reject_clearance` MCP tool."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _seed_under_review_clearance(
    client: TestClient,
    session_headers: dict[str, str],
) -> str:
    """Walk a clearance from Defined to UnderReview via MCP tools."""

    def _call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 100,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
            headers=session_headers,
        )
        assert response.status_code == 200
        body = parse_sse_data(response.text)
        assert body["result"]["isError"] is False, body
        return body["result"]

    register = _call(
        "register_clearance",
        {
            "kind": "ESAF",
            "facility_asset_id": str(uuid4()),
            "title": "Pilot",
            "bindings": [{"kind": "Run", "id": str(uuid4())}],
        },
    )
    cid = str(register["structuredContent"]["clearance_id"])
    _call("submit_clearance", {"clearance_id": cid})
    _call(
        "start_review_clearance",
        {"clearance_id": cid, "first_reviewer_role": "ESH"},
    )
    return cid


@pytest.mark.contract
def test_mcp_lists_reject_clearance_tool() -> None:
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
    assert "reject_clearance" in tool_names


@pytest.mark.contract
def test_mcp_reject_clearance_tool_returns_structured_clearance_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        cid = _seed_under_review_clearance(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "reject_clearance",
                    "arguments": {
                        "clearance_id": cid,
                        "reason": "ESRB found insufficient PPE specification",
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["clearance_id"] == cid


@pytest.mark.contract
def test_mcp_reject_clearance_tool_returns_iserror_on_whitespace_reason() -> None:
    """Whitespace-only reason passes Pydantic min_length=1 but trips the VO."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        cid = _seed_under_review_clearance(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "reject_clearance",
                    "arguments": {"clearance_id": cid, "reason": "   "},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_reject_clearance_tool_returns_iserror_when_not_under_review() -> None:
    """Reject from Defined (no submit/start_review) -> ClearanceCannotRejectError."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        register = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 100,
                "method": "tools/call",
                "params": {
                    "name": "register_clearance",
                    "arguments": {
                        "kind": "ESAF",
                        "facility_asset_id": str(uuid4()),
                        "title": "Pilot",
                        "bindings": [{"kind": "Run", "id": str(uuid4())}],
                    },
                },
            },
            headers=session_headers,
        )
        cid = str(parse_sse_data(register.text)["result"]["structuredContent"]["clearance_id"])
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "reject_clearance",
                    "arguments": {"clearance_id": cid, "reason": "premature rejection"},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
