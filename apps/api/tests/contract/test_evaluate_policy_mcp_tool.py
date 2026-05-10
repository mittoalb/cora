"""Contract tests for the `evaluate_policy` MCP tool."""

import json
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}

_CONDUIT = "01900000-0000-7000-8000-00000000aaaa"
_OTHER_CONDUIT = "01900000-0000-7000-8000-00000000bbbb"
_ALLOWED_PRINCIPAL = "01900000-0000-7000-8000-000000000a01"
_OTHER_PRINCIPAL = "01900000-0000-7000-8000-000000000a02"


def _parse_sse_data(text: str) -> dict[str, Any]:
    for line in text.splitlines():
        if line.startswith("data:"):
            payload = line[len("data:") :].strip()
            return json.loads(payload)
    msg = f"No SSE data: line in response body: {text!r}"
    raise AssertionError(msg)


def _open_session(client: TestClient) -> dict[str, str]:
    init = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "contract-test", "version": "0.1"},
            },
        },
        headers=_HEADERS,
    )
    assert init.status_code == 200
    session_id = init.headers["mcp-session-id"]
    headers_with_session = {**_HEADERS, "mcp-session-id": session_id}
    notif = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=headers_with_session,
    )
    assert notif.status_code == 202
    return headers_with_session


def _define_policy_via_rest(client: TestClient) -> str:
    """Reuse the REST endpoint to seed a policy. Same in-process
    in-memory store backs both REST and MCP via the lifespan."""
    response = client.post(
        "/policies",
        json={
            "name": "Beam-team",
            "conduit_id": _CONDUIT,
            "permitted_principals": [_ALLOWED_PRINCIPAL],
            "permitted_commands": ["RegisterActor"],
        },
    )
    assert response.status_code == 201
    policy_id: str = response.json()["policy_id"]
    return policy_id


def _call_evaluate_tool(
    client: TestClient,
    headers: dict[str, str],
    *,
    policy_id: str,
    subject_principal_id: str = _ALLOWED_PRINCIPAL,
    subject_command_name: str = "RegisterActor",
    subject_conduit_id: str = _CONDUIT,
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/call",
            "params": {
                "name": "evaluate_policy",
                "arguments": {
                    "policy_id": policy_id,
                    "subject_principal_id": subject_principal_id,
                    "subject_command_name": subject_command_name,
                    "subject_conduit_id": subject_conduit_id,
                },
            },
        },
        headers=headers,
    )
    assert response.status_code == 200
    return _parse_sse_data(response.text)


@pytest.mark.contract
def test_mcp_lists_evaluate_policy_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = _open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    assert response.status_code == 200
    body = _parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "evaluate_policy" in tool_names


@pytest.mark.contract
def test_mcp_evaluate_policy_returns_allow_for_matching_subject() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy_via_rest(client)
        session_headers = _open_session(client)
        body = _call_evaluate_tool(client, session_headers, policy_id=policy_id)
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["decision"] == "Allow"
    assert result["structuredContent"]["reason"] is None


@pytest.mark.contract
def test_mcp_evaluate_policy_returns_deny_with_reason() -> None:
    with TestClient(create_app()) as client:
        policy_id = _define_policy_via_rest(client)
        session_headers = _open_session(client)
        body = _call_evaluate_tool(
            client,
            session_headers,
            policy_id=policy_id,
            subject_principal_id=_OTHER_PRINCIPAL,
        )
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["decision"] == "Deny"
    assert result["structuredContent"]["reason"] is not None


@pytest.mark.contract
def test_mcp_evaluate_policy_returns_iserror_when_policy_missing() -> None:
    """Missing policy → handler returns None → tool raises ValueError →
    FastMCP wraps as isError: true (matches REST 404 in MCP idiom)."""
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        session_headers = _open_session(client)
        body = _call_evaluate_tool(client, session_headers, policy_id=missing_id)
    result = body["result"]
    assert result["isError"] is True
    assert "not found" in result["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_evaluate_policy_returns_iserror_on_invalid_uuid_argument() -> None:
    """FastMCP's input-schema validation rejects non-UUID strings."""
    with TestClient(create_app()) as client:
        session_headers = _open_session(client)
        body = _call_evaluate_tool(
            client,
            session_headers,
            policy_id="not-a-uuid",
        )
    assert body["result"]["isError"] is True
