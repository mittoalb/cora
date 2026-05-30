"""Contract tests for the `list_credentials` MCP tool.

Vault hygiene: the structured-output schema MUST NOT carry opaque
secret material refs; `get_credential` is the path for ref inspection.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_list_credentials_tool() -> None:
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
    assert "list_credentials" in tool_names


@pytest.mark.contract
def test_mcp_list_credentials_tool_returns_empty_page() -> None:
    """In-memory app has no pool; tool returns empty items + null cursor."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "list_credentials", "arguments": {}},
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    structured = body["result"]["structuredContent"]
    assert structured["items"] == []
    assert structured["next_cursor"] is None


@pytest.mark.contract
def test_mcp_list_credentials_tool_accepts_filters() -> None:
    """Tool accepts all 3 filters plus pagination params without error."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "list_credentials",
                    "arguments": {
                        "facility_id": "aps-2bm",
                        "purpose": "Signing",
                        "status": "Active",
                        "limit": 25,
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["structuredContent"]["items"] == []


@pytest.mark.contract
def test_mcp_list_credentials_tool_rejects_invalid_purpose() -> None:
    """Closed-enum filter rejects unknown values."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "list_credentials",
                    "arguments": {"purpose": "Mystery"},
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert "error" in body or body["result"].get("isError") is True


@pytest.mark.contract
def test_mcp_list_credentials_tool_output_schema_omits_opaque_refs() -> None:
    """Vault hygiene: structured-output schema MUST NOT carry opaque secret
    material refs. Inspects the per-item property names in the tool's
    outputSchema, not free-text description fields."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 6, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool: dict[str, Any] = next(
        t for t in body["result"]["tools"] if t["name"] == "list_credentials"
    )
    output_schema: dict[str, Any] = tool.get("outputSchema") or {}
    defs: dict[str, Any] = output_schema.get("$defs") or {}
    item_schema: dict[str, Any] = defs.get("CredentialSummaryItemOutput") or {}
    raw_properties: dict[str, Any] = item_schema.get("properties") or {}
    properties: set[str] = set(raw_properties.keys())
    forbidden = {
        "secret_ref",
        "public_material_ref",
        "rotation_pending_secret_ref",
        "rotation_pending_public_material_ref",
    }
    assert forbidden.isdisjoint(properties), properties & forbidden
