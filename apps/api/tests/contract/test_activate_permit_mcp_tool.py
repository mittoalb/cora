"""Contract tests for the `activate_permit` MCP tool.

Mirrors `test_activate_asset_mcp_tool.py`. Shared MCP helpers live
in `tests/contract/_mcp_helpers.py`.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_permit_arguments() -> dict[str, Any]:
    return {
        "peer_facility_id": "aps-2bm",
        "direction": "Outbound",
        "allowed_credential_ids": [str(uuid4())],
        "allowed_payload_types": ["application/vnd.cora.dataset+json"],
        "allowed_artifact_kinds": ["dataset"],
        "abi_tier_floor": "Stable",
        "expires_at": "2027-05-30T12:00:00+00:00",
        "terms": {
            "kind": "Outbound",
            "scopes": [{"kind": "dataset", "name": "alpha", "qualifier": None}],
            "read_scope": "ReadAllArtifacts",
            "onward_action_scope": "ReadOnly",
        },
    }


def _define_permit_via_tool(client: TestClient, headers: dict[str, str]) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "define_permit",
                "arguments": _define_permit_arguments(),
            },
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False, body
    return UUID(body["result"]["structuredContent"]["permit_id"])


@pytest.mark.contract
def test_mcp_lists_activate_permit_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "activate_permit" in tool_names


@pytest.mark.contract
def test_mcp_activate_permit_tool_succeeds_for_defined_permit() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        permit_id = _define_permit_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "activate_permit",
                    "arguments": {"permit_id": str(permit_id)},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False, body
    assert body["result"]["structuredContent"]["permit_id"] == str(permit_id)


@pytest.mark.contract
def test_mcp_activate_permit_tool_returns_iserror_for_unknown_permit() -> None:
    """PermitNotFoundError propagates -> FastMCP wraps as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "activate_permit",
                    "arguments": {"permit_id": str(uuid4())},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_activate_permit_tool_returns_iserror_when_already_active() -> None:
    """PermitCannotActivateError on Active permit -> isError. Same shape
    as the REST 409 response."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        permit_id = _define_permit_via_tool(client, headers)
        first = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "activate_permit",
                    "arguments": {"permit_id": str(permit_id)},
                },
            },
            headers=headers,
        )
        assert parse_sse_data(first.text)["result"]["isError"] is False

        second = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "activate_permit",
                    "arguments": {"permit_id": str(permit_id)},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(second.text)
    assert body["result"]["isError"] is True
    text = body["result"]["content"][0]["text"]
    assert "Active" in text
    assert "Defined" in text


@pytest.mark.contract
def test_mcp_activate_permit_tool_rejects_missing_required_argument() -> None:
    """Pydantic-layer rejection bubbles as isError: true via FastMCP."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "activate_permit",
                    "arguments": {},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
