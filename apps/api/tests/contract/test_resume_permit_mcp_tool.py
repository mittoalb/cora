"""Contract tests for the `resume_permit` MCP tool.

Single-source reversible transition: `Suspended -> Active`. Strict-
not-idempotent: resuming an already-Active (or Defined / Revoked)
permit surfaces as MCP `isError: true` (mapped from
`PermitCannotResumeError`).
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_args() -> dict[str, Any]:
    return {
        "peer_facility_id": "aps-2bm",
        "direction": "Outbound",
        "allowed_credentials": [str(uuid4())],
        "allowed_payload_types": ["application/json"],
        "allowed_artifact_kinds": ["dataset"],
        "abi_tier_floor": "Stable",
        "expires_at": "2030-01-01T00:00:00+00:00",
        "terms": {
            "kind": "Outbound",
            "scope_set": [{"kind": "dataset", "name": "public", "qualifier": None}],
            "read_scope": "ReadAllArtifacts",
            "onward_action_scope": "ReadOnly",
        },
    }


def _define_permit_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {"name": "define_permit", "arguments": _register_args()},
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False, body
    return UUID(body["result"]["structuredContent"]["permit_id"])


def _call_tool(
    client: TestClient,
    headers: dict[str, str],
    *,
    rpc_id: int,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers=headers,
    )
    assert response.status_code == 200
    return parse_sse_data(response.text)


def _drive_to_suspended(client: TestClient, headers: dict[str, str]) -> UUID:
    permit_id = _define_permit_via_tool(client, headers)
    activate = _call_tool(
        client,
        headers,
        rpc_id=101,
        name="activate_permit",
        arguments={"permit_id": str(permit_id)},
    )
    assert activate["result"]["isError"] is False, activate
    suspend = _call_tool(
        client,
        headers,
        rpc_id=102,
        name="suspend_permit",
        arguments={"permit_id": str(permit_id)},
    )
    assert suspend["result"]["isError"] is False, suspend
    return permit_id


@pytest.mark.contract
def test_mcp_lists_resume_permit_tool() -> None:
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
    assert "resume_permit" in tool_names


@pytest.mark.contract
def test_mcp_resume_permit_tool_succeeds_from_suspended() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        permit_id = _drive_to_suspended(client, session_headers)
        body = _call_tool(
            client,
            session_headers,
            rpc_id=3,
            name="resume_permit",
            arguments={"permit_id": str(permit_id)},
        )
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["permit_id"] == str(permit_id)


@pytest.mark.contract
def test_mcp_resume_permit_tool_is_strict_not_idempotent_from_active() -> None:
    """Resuming an already-Active permit surfaces as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        permit_id = _define_permit_via_tool(client, session_headers)
        activate = _call_tool(
            client,
            session_headers,
            rpc_id=3,
            name="activate_permit",
            arguments={"permit_id": str(permit_id)},
        )
        assert activate["result"]["isError"] is False
        body = _call_tool(
            client,
            session_headers,
            rpc_id=4,
            name="resume_permit",
            arguments={"permit_id": str(permit_id)},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_resume_permit_tool_returns_iserror_when_defined() -> None:
    """`Defined` permits need `activate_permit`; resume returns isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        permit_id = _define_permit_via_tool(client, session_headers)
        body = _call_tool(
            client,
            session_headers,
            rpc_id=3,
            name="resume_permit",
            arguments={"permit_id": str(permit_id)},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_resume_permit_tool_returns_iserror_for_unknown_permit() -> None:
    """Calling `resume_permit` on an unknown id surfaces as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        body = _call_tool(
            client,
            session_headers,
            rpc_id=5,
            name="resume_permit",
            arguments={"permit_id": str(uuid4())},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_resume_permit_tool_rejects_missing_permit_id() -> None:
    """Pydantic-layer rejection bubbles as isError: true via FastMCP."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        body = _call_tool(
            client,
            session_headers,
            rpc_id=6,
            name="resume_permit",
            arguments={},
        )
    assert body["result"]["isError"] is True
