"""Contract tests for the `initialize_seal` MCP tool.

Pins tool registration, happy-path structured output (seal_stream_id
+ facility_id), and error-path bubbling (isError true on missing
args, on malformed UUID args, and on decider-layer key-collision
rejection).

The happy-path test seeds the in-memory `CredentialLookup` adapter so
the handler's cross-aggregate purpose-binding + status-Active checks
(Pass 3) pass.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.credential import CredentialPurpose, CredentialStatus
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from tests.contract._mcp_helpers import open_session, parse_sse_data

_ONLINE_KEY_REF = "01900000-0000-7000-8000-00000000c0a1"
_OFFLINE_KEY_REF = "01900000-0000-7000-8000-00000000c0b1"


def _args(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "facility_id": f"aps-2bm-{uuid4().hex[:8]}",
        "online_credential_id": _ONLINE_KEY_REF,
        "offline_credential_id": _OFFLINE_KEY_REF,
    }
    base.update(overrides)
    return base


def _seed_active_credentials(app: FastAPI, *, facility_id: str) -> None:
    lookup = app.state.deps.credential_lookup
    lookup.register(
        credential_id=UUID(_ONLINE_KEY_REF),
        facility_id=facility_id,
        purpose=CredentialPurpose.SEAL_ONLINE_SIGNING.value,
        status=CredentialStatus.ACTIVE.value,
    )
    lookup.register(
        credential_id=UUID(_OFFLINE_KEY_REF),
        facility_id=facility_id,
        purpose=CredentialPurpose.SEAL_OFFLINE_ROOT.value,
        status=CredentialStatus.ACTIVE.value,
    )


@pytest.mark.contract
def test_mcp_lists_initialize_seal_tool() -> None:
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
    assert "initialize_seal" in tool_names


@pytest.mark.contract
def test_mcp_initialize_seal_tool_returns_structured_stream_id_and_facility_id() -> None:
    args = _args()
    app = create_app()
    with TestClient(app) as client:
        _seed_active_credentials(app, facility_id=args["facility_id"])
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "initialize_seal", "arguments": args},
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    structured = result["structuredContent"]
    assert structured["facility_id"] == args["facility_id"]
    assert UUID(structured["seal_stream_id"]) == seal_stream_id(args["facility_id"])


@pytest.mark.contract
def test_mcp_initialize_seal_tool_returns_iserror_on_key_collision() -> None:
    """Decider-layer SealKeyCollisionError surfaces through FastMCP as isError: true."""
    shared = "01900000-0000-7000-8000-00000000ccc1"
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "initialize_seal",
                    "arguments": _args(online_credential_id=shared, offline_credential_id=shared),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_initialize_seal_tool_rejects_missing_required_argument() -> None:
    """Pydantic-layer rejection (facility_id missing) bubbles as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        args = _args()
        del args["facility_id"]
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "initialize_seal",
                    "arguments": args,
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_initialize_seal_tool_rejects_malformed_uuid_argument() -> None:
    """Pydantic rejects an online_credential_id that does not parse as UUID;
    surfaces as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "initialize_seal",
                    "arguments": _args(online_credential_id="not-a-uuid"),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
