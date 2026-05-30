"""Contract tests for the `get_seal` MCP tool.

Pins tool registration, happy-path structured output (per-facility
singleton fields keyed on `facility_id`), and the null-on-miss path
(FastMCP wraps `T | None` returns under `structuredContent.result`).
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_ONLINE_KEY_REF = "01900000-0000-7000-8000-00000000c0a1"
_OFFLINE_KEY_REF = "01900000-0000-7000-8000-00000000c0b1"


def _initialize_args(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "facility_id": f"aps-2bm-{uuid4().hex[:8]}",
        "online_key_ref": _ONLINE_KEY_REF,
        "offline_key_ref": _OFFLINE_KEY_REF,
    }
    base.update(overrides)
    return base


def _seed_seal(client: TestClient, session_headers: dict[str, str]) -> str:
    args = _initialize_args()
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "initialize_seal", "arguments": args},
        },
        headers=session_headers,
    )
    assert response.status_code == 200, response.text
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False, body
    return str(args["facility_id"])


@pytest.mark.contract
def test_mcp_lists_get_seal_tool() -> None:
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
    assert "get_seal" in tool_names


@pytest.mark.contract
def test_mcp_get_seal_tool_returns_full_structured_state() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        facility_id = _seed_seal(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_seal",
                    "arguments": {"facility_id": facility_id},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    # FastMCP wraps `T | None` return types under a `result` slot in
    # structuredContent (see test_mcp_get_seal_tool_returns_null_on_miss).
    payload = result["structuredContent"]["result"]
    assert payload is not None
    assert payload["facility_id"] == facility_id
    assert payload["online_key_ref"] == _ONLINE_KEY_REF
    assert payload["offline_key_ref"] == _OFFLINE_KEY_REF
    assert payload["current_head_hash"] is None
    assert payload["current_sequence_number"] == 0
    assert payload["status"] == "Live"


@pytest.mark.contract
def test_mcp_get_seal_tool_returns_null_on_miss() -> None:
    """Tool returns null for unknown facility_id (matches REST 404 semantically)."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_seal",
                    "arguments": {"facility_id": f"no-such-facility-{uuid4().hex[:8]}"},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    # FastMCP serializes None as null in the structured content payload.
    assert result["structuredContent"]["result"] is None


@pytest.mark.contract
def test_mcp_get_seal_tool_rejects_empty_facility_id() -> None:
    """`min_length=1` on the facility_id argument bubbles as isError: true
    when an empty string is passed."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "get_seal",
                    "arguments": {"facility_id": ""},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


# Silence the unused-import linter.
_ = UUID
