"""Contract tests for the `approve_clearance` MCP tool."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.safety.aggregates.clearance_template import clearance_template_stream_id
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _seed_under_review_clearance(
    client: TestClient,
    session_headers: dict[str, str],
    *,
    with_approved_step: bool = True,
) -> str:
    """Walk a clearance from Defined to UnderReview via MCP tools.

    When `with_approved_step` is true, also append a single Approved
    review step so the chain is ready for `approve_clearance`.
    """

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

    template_id = clearance_template_stream_id("cora", "ESAF")
    register = _call(
        "register_clearance",
        {
            "template_id": str(template_id),
            "facility_code": "cora",
            "title": "Pilot",
            "bindings": [{"kind": "Run", "id": str(uuid4())}],
        },
    )
    cid = str(register["structuredContent"]["clearance_id"])
    _call("submit_clearance", {"clearance_id": cid})
    _call(
        "start_clearance_review",
        {"clearance_id": cid, "first_reviewer_role": "ESH"},
    )
    if with_approved_step:
        _call(
            "append_clearance_review_step",
            {
                "clearance_id": cid,
                "step_index": 0,
                "role": "ESH",
                "decision": "Approved",
                "decided_at": "2026-05-15T12:00:00+00:00",
            },
        )
    return cid


@pytest.mark.contract
def test_mcp_lists_approve_clearance_tool() -> None:
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
    assert "approve_clearance" in tool_names


@pytest.mark.contract
def test_mcp_approve_clearance_tool_returns_structured_clearance_id() -> None:
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
                    "name": "approve_clearance",
                    "arguments": {"clearance_id": cid},
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
def test_mcp_approve_clearance_tool_returns_iserror_when_no_terminal_approved_step() -> None:
    """Chain ends in something other than Approved -> handler raises
    ClearanceCannotApproveError; FastMCP wraps as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        cid = _seed_under_review_clearance(client, session_headers, with_approved_step=False)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "approve_clearance",
                    "arguments": {"clearance_id": cid},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_approve_clearance_tool_carries_validity_window_overrides() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        cid = _seed_under_review_clearance(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "approve_clearance",
                    "arguments": {
                        "clearance_id": cid,
                        "valid_from": "2026-06-01T00:00:00+00:00",
                        "valid_until": "2026-09-01T00:00:00+00:00",
                    },
                },
            },
            headers=session_headers,
        )
        assert response.status_code == 200
        body = parse_sse_data(response.text)
        assert body["result"]["isError"] is False

        # Verify the window landed via a follow-up get_clearance call within
        # the same MCP session.
        get_response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "get_clearance",
                    "arguments": {"clearance_id": cid},
                },
            },
            headers=session_headers,
        )
        assert get_response.status_code == 200
        get_body = parse_sse_data(get_response.text)
        structured = get_body["result"]["structuredContent"]
        assert structured["status"] == "Approved"
        assert structured["valid_from"] == "2026-06-01T00:00:00Z"
        assert structured["valid_until"] == "2026-09-01T00:00:00Z"
