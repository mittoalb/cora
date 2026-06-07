"""Contract tests for the `rate_decision` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _seed_decision_via_rest(client: TestClient) -> str:
    """Use REST to register an Actor + Decision; returns the decision_id."""
    actor = client.post("/actors", json={"name": "Decider"})
    assert actor.status_code == 201
    decision = client.post(
        "/decisions",
        json={
            "decided_by": actor.json()["actor_id"],
            "context": "RunDebrief",
            "choice": "NominalCompletion",
        },
    )
    assert decision.status_code == 201
    return decision.json()["decision_id"]


@pytest.mark.contract
def test_mcp_lists_rate_decision_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        r = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(r.text)
    names = [t["name"] for t in body["result"]["tools"]]
    assert "rate_decision" in names


@pytest.mark.contract
def test_mcp_rate_decision_returns_structured_decision_id() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        decision_id = _seed_decision_via_rest(client)
        r = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "rate_decision",
                    "arguments": {"decision_id": decision_id, "rating": "useful"},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(r.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["decision_id"] == decision_id
    UUID(result["structuredContent"]["decision_id"])


@pytest.mark.contract
def test_mcp_rate_decision_with_comment() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        decision_id = _seed_decision_via_rest(client)
        r = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "rate_decision",
                    "arguments": {
                        "decision_id": decision_id,
                        "rating": "misleading",
                        "comment": "missed the temperature excursion",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(r.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_rate_decision_returns_iserror_on_unknown_id() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        r = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "rate_decision",
                    "arguments": {"decision_id": str(uuid4()), "rating": "useful"},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(r.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_rate_decision_returns_iserror_on_whitespace_only_comment() -> None:
    """Whitespace-only comment trips the domain VO; FastMCP wraps as
    isError: true."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        decision_id = _seed_decision_via_rest(client)
        r = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "rate_decision",
                    "arguments": {
                        "decision_id": decision_id,
                        "rating": "useful",
                        "comment": "   ",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(r.text)
    assert body["result"]["isError"] is True
