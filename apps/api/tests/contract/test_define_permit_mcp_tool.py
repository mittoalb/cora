"""Contract tests for the `define_permit` MCP tool.

Pins tool registration, happy-path structured output (permit_id),
and error-path bubbling (isError true on missing args and on
decider-layer rejection)."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_EXPIRES_AT = datetime(2027, 1, 1, 0, 0, 0, tzinfo=UTC).isoformat()


def _args(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "peer_facility_code": "aps-2bm",
        "direction": "Outbound",
        "allowed_credential_ids": [str(uuid4())],
        "allowed_payload_types": ["application/json"],
        "allowed_artifact_kinds": ["dataset"],
        "abi_tier_floor": "Stable",
        "expires_at": _EXPIRES_AT,
        "terms": {
            "kind": "Outbound",
            "scopes": [{"kind": "dataset", "name": "public"}],
            "read_scope": "ReadAllArtifacts",
            "onward_action_scope": "ReadOnly",
        },
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_mcp_lists_define_permit_tool() -> None:
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
    assert "define_permit" in tool_names


@pytest.mark.contract
def test_mcp_define_permit_tool_returns_structured_permit_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "define_permit", "arguments": _args()},
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert "permit_id" in result["structuredContent"]
    UUID(result["structuredContent"]["permit_id"])


@pytest.mark.contract
def test_mcp_define_permit_tool_returns_iserror_on_expires_at_in_past() -> None:
    """Decider-layer InvalidPermitScopeError surfaces through FastMCP as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "define_permit",
                    "arguments": _args(
                        expires_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC).isoformat(),
                    ),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_define_permit_tool_returns_iserror_on_outbound_terms_collapse() -> None:
    """PermitScopeCollapseError surfaces through FastMCP as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "define_permit",
                    "arguments": _args(
                        terms={
                            "kind": "Outbound",
                            "scopes": [{"kind": "dataset", "name": "public"}],
                            "read_scope": "ListMetadataOnly",
                            "onward_action_scope": "MayExportOffPlatform",
                        },
                    ),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_define_permit_tool_rejects_missing_required_argument() -> None:
    """Pydantic-layer rejection (peer_facility_code missing) bubbles as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        args = _args()
        del args["peer_facility_code"]
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "define_permit",
                    "arguments": args,
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
