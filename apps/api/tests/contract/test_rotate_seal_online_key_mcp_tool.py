"""Contract tests for the `rotate_seal_online_key` MCP tool.

Mirrors the REST endpoint contract through the MCP surface: pins tool
listing, structured-content shape on the happy path (via handler
override), and the `isError: true` mapping for the decider-layer FSM
rejection (Republishing or no-op rotation), the key-collision branch,
and the unknown-seal branch.

The happy-path Live -> Live transition is exercised end-to-end by the
handler test and the Postgres integration test; this file only
exercises the tool wire (FastMCP shape, status mapping).
"""

from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.seal import (
    SealCannotRotateError,
    SealKeyCollisionError,
    SealNotFoundError,
    SealStatus,
)
from cora.federation.features.rotate_seal_online_key.handler import Handler
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _call_tool(
    client: TestClient,
    *,
    headers: dict[str, str],
    request_id: int,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return parse_sse_data(response.text)


def _override_handler(app: object, handler: Handler) -> None:
    """Override the MCP-bound handler bundle so the tool returns the fake."""
    state = cast("object", app.state.federation)  # type: ignore[attr-defined]
    object.__setattr__(state, "rotate_seal_online_key", handler)


@pytest.mark.contract
def test_mcp_lists_rotate_seal_online_key_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "rotate_seal_online_key" in tool_names


@pytest.mark.contract
def test_mcp_rotate_seal_online_key_tool_returns_structured_ids() -> None:
    """Happy path via handler override: tool returns structured
    facility_code + new_online_credential_id (matches REST 204 + body contract)."""
    app = create_app()
    new_online_credential_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=20,
            name="rotate_seal_online_key",
            arguments={
                "facility_code": "aps-2bm",
                "new_online_credential_id": str(new_online_credential_id),
                "signed_by_offline_root": True,
            },
        )
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["facility_code"] == "aps-2bm"
    assert result["structuredContent"]["new_online_credential_id"] == str(new_online_credential_id)
    assert result["structuredContent"]["signed_by_offline_root"] is True
    UUID(result["structuredContent"]["new_online_credential_id"])


@pytest.mark.contract
def test_mcp_rotate_seal_online_key_tool_returns_iserror_when_republishing() -> None:
    """Decider-layer FSM rejection (Republishing) surfaces through FastMCP
    as isError: true."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealCannotRotateError("aps-2bm", SealStatus.REPUBLISHING)

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=30,
            name="rotate_seal_online_key",
            arguments={
                "facility_code": "aps-2bm",
                "new_online_credential_id": str(uuid4()),
                "signed_by_offline_root": True,
            },
        )
    assert body["result"]["isError"] is True
    assert "rotate" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_rotate_seal_online_key_tool_returns_iserror_on_noop_rotation() -> None:
    """Decider-layer FSM rejection (no-op rotation) surfaces through FastMCP."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealCannotRotateError("aps-2bm", SealStatus.LIVE)

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=35,
            name="rotate_seal_online_key",
            arguments={
                "facility_code": "aps-2bm",
                "new_online_credential_id": str(uuid4()),
                "signed_by_offline_root": True,
            },
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_rotate_seal_online_key_tool_returns_iserror_on_key_collision() -> None:
    """Key-separation invariant violation surfaces through FastMCP."""
    app = create_app()
    shared_ref = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealKeyCollisionError(facility_id="aps-2bm", shared_credential_id=shared_ref)

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=40,
            name="rotate_seal_online_key",
            arguments={
                "facility_code": "aps-2bm",
                "new_online_credential_id": str(shared_ref),
                "signed_by_offline_root": True,
            },
        )
    assert body["result"]["isError"] is True
    assert "differ" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_rotate_seal_online_key_tool_returns_iserror_on_unknown_seal() -> None:
    """A handler raising SealNotFoundError surfaces through FastMCP."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealNotFoundError("aps-2bm")

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=50,
            name="rotate_seal_online_key",
            arguments={
                "facility_code": "aps-2bm",
                "new_online_credential_id": str(uuid4()),
                "signed_by_offline_root": True,
            },
        )
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_rotate_seal_online_key_tool_rejects_missing_required_argument() -> None:
    """Pydantic-layer rejection (missing new_online_credential_id) bubbles as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=60,
            name="rotate_seal_online_key",
            arguments={"facility_code": "aps-2bm"},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_rotate_seal_online_key_tool_rejects_malformed_uuid() -> None:
    """Pydantic-layer rejection (non-UUID new_online_credential_id) bubbles as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=70,
            name="rotate_seal_online_key",
            arguments={
                "facility_code": "aps-2bm",
                "new_online_credential_id": "not-a-uuid",
                "signed_by_offline_root": True,
            },
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_rotate_seal_online_key_tool_rejects_missing_signed_by_offline_root() -> None:
    """Pydantic-layer rejection (missing signed_by_offline_root) bubbles as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=80,
            name="rotate_seal_online_key",
            arguments={
                "facility_code": "aps-2bm",
                "new_online_credential_id": str(uuid4()),
            },
        )
    assert body["result"]["isError"] is True
