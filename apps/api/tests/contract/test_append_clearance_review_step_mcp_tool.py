"""Contract tests for the `append_clearance_review_step` MCP tool."""

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
def test_mcp_lists_append_clearance_review_step_tool() -> None:
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
    assert "append_clearance_review_step" in tool_names


@pytest.mark.contract
def test_mcp_append_clearance_review_step_tool_returns_structured_index() -> None:
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
                    "name": "append_clearance_review_step",
                    "arguments": {
                        "clearance_id": cid,
                        "step_index": 0,
                        "role": "ESH",
                        "decision": "Approved",
                        "decided_at": "2026-05-15T12:00:00+00:00",
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
    assert result["structuredContent"]["step_index"] == 0


@pytest.mark.contract
def test_mcp_append_clearance_review_step_tool_returns_iserror_on_wrong_step_index() -> None:
    """step_index out-of-order trips the append-only contract at the decider."""
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
                    "name": "append_clearance_review_step",
                    "arguments": {
                        "clearance_id": cid,
                        "step_index": 5,
                        "role": "ESH",
                        "decision": "Approved",
                        "decided_at": "2026-05-15T12:00:00+00:00",
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_append_clearance_review_step_tool_returns_iserror_on_future_decided_at() -> None:
    """Future-dated decided_at trips the chain time invariant."""
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
                    "name": "append_clearance_review_step",
                    "arguments": {
                        "clearance_id": cid,
                        "step_index": 0,
                        "role": "ESH",
                        "decision": "Approved",
                        "decided_at": "2099-01-01T00:00:00+00:00",
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
