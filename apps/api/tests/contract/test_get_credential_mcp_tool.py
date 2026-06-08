"""Contract tests for the `get_credential` MCP tool.

Pins tool registration, structured hit-state (with opaque-pointer
hygiene from the locked design AH#6), and null-on-miss semantics
that mirror the REST 404. FastMCP wraps `T | None` returns under
a `result` slot in structuredContent (see get_calibration tool
precedent).
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC).isoformat()


def _register_args() -> dict[str, Any]:
    return {
        "facility_code": "aps-2bm",
        "audience": "peer.example.org",
        "purpose": "Signing",
        "secret_ref": "vault://kv/cora/federation/aps-2bm/signing#v1",
        "public_material_ref": "vault://kv/cora/federation/aps-2bm/signing/pub#v1",
        "expires_at": _EXPIRES_AT,
    }


def _seed_credential(client: TestClient, session_headers: dict[str, str]) -> str:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "register_credential", "arguments": _register_args()},
        },
        headers=session_headers,
    )
    assert response.status_code == 200, response.text
    body = parse_sse_data(response.text)
    return str(body["result"]["structuredContent"]["credential_id"])


@pytest.mark.contract
def test_mcp_lists_get_credential_tool() -> None:
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
    assert "get_credential" in tool_names


@pytest.mark.contract
def test_mcp_get_credential_tool_returns_full_structured_state() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        cid = _seed_credential(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_credential",
                    "arguments": {"credential_id": cid},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    # FastMCP wraps `T | None` return types under a `result` slot in
    # structuredContent (see get_calibration tool precedent).
    payload = result["structuredContent"]["result"]
    assert payload is not None
    assert payload["id"] == cid
    assert payload["facility_code"] == "aps-2bm"
    assert payload["audience"] == "peer.example.org"
    assert payload["purpose"] == "Signing"
    assert payload["secret_ref"] == _register_args()["secret_ref"]
    assert payload["public_material_ref"] == _register_args()["public_material_ref"]
    assert payload["status"] == "Active"
    assert payload["rotation_pending_secret_ref"] is None
    assert payload["rotation_pending_public_material_ref"] is None


@pytest.mark.contract
def test_mcp_get_credential_tool_returns_null_on_miss() -> None:
    """Tool returns null for unknown credential_id (matches REST 404 semantically)."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_credential",
                    "arguments": {"credential_id": str(uuid4())},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    # FastMCP serialises None as null in the structured content payload.
    assert result["structuredContent"]["result"] is None


# Silence the unused-import linter for the optional UUID symbol.
_ = UUID
