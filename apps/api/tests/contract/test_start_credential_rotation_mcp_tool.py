"""Contract tests for the `start_credential_rotation` MCP tool.

Pin tool listing, structured-content shape on the happy path (via
handler override), and the `isError: true` mappings for the decider-
layer FSM rejection plus the unknown-credential branch plus
Pydantic-layer rejection (missing `new_secret_ref`, empty
`new_secret_ref`).
"""

from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.credential import (
    CredentialCannotRotateError,
    CredentialNotFoundError,
    CredentialStatus,
)
from cora.federation.features.start_credential_rotation.handler import Handler
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
    object.__setattr__(state, "start_credential_rotation", handler)


@pytest.mark.contract
def test_mcp_lists_start_credential_rotation_tool() -> None:
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
    assert "start_credential_rotation" in tool_names


@pytest.mark.contract
def test_mcp_start_credential_rotation_tool_returns_structured_credential_id() -> None:
    """Happy path via handler override: tool returns structured credential_id
    (matches REST 204 + path-id contract)."""
    app = create_app()
    credential_id = uuid4()

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
            name="start_credential_rotation",
            arguments={
                "credential_id": str(credential_id),
                "new_secret_ref": "vault://pending/v2",
                "new_public_material_ref": "vault://pending/pub/v2",
            },
        )
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["credential_id"] == str(credential_id)
    UUID(result["structuredContent"]["credential_id"])


@pytest.mark.contract
def test_mcp_start_credential_rotation_tool_accepts_omitted_public_material_ref() -> None:
    """`new_public_material_ref` is optional; omitting it succeeds."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=21,
            name="start_credential_rotation",
            arguments={
                "credential_id": str(uuid4()),
                "new_secret_ref": "vault://pending/v2",
            },
        )
    assert body["result"]["isError"] is False, body


@pytest.mark.contract
def test_mcp_start_credential_rotation_tool_returns_iserror_on_rotating_credential() -> None:
    """Decider-layer FSM rejection (Rotating != Active) surfaces through
    FastMCP as isError: true."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise CredentialCannotRotateError(
            UUID(int=1),
            CredentialStatus.ROTATING,
            "start_rotation",
        )

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=30,
            name="start_credential_rotation",
            arguments={
                "credential_id": str(uuid4()),
                "new_secret_ref": "vault://pending/v3",
            },
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_start_credential_rotation_tool_returns_iserror_on_revoked_credential() -> None:
    """Revoked is terminal; start_rotation surfaces through FastMCP as isError."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise CredentialCannotRotateError(
            UUID(int=2),
            CredentialStatus.REVOKED,
            "start_rotation",
        )

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=31,
            name="start_credential_rotation",
            arguments={
                "credential_id": str(uuid4()),
                "new_secret_ref": "vault://pending/v2",
            },
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_start_credential_rotation_tool_returns_iserror_on_unknown_credential() -> None:
    """A handler raising CredentialNotFoundError surfaces through FastMCP."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise CredentialNotFoundError(UUID(int=0))

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=40,
            name="start_credential_rotation",
            arguments={
                "credential_id": str(uuid4()),
                "new_secret_ref": "vault://pending/v2",
            },
        )
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_start_credential_rotation_tool_rejects_missing_credential_id() -> None:
    """Pydantic-layer rejection (missing credential_id) bubbles as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=60,
            name="start_credential_rotation",
            arguments={"new_secret_ref": "vault://pending/v2"},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_start_credential_rotation_tool_rejects_missing_new_secret_ref() -> None:
    """Pydantic-layer rejection (missing new_secret_ref) bubbles as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=61,
            name="start_credential_rotation",
            arguments={"credential_id": str(uuid4())},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_start_credential_rotation_tool_rejects_empty_new_secret_ref() -> None:
    """Pydantic min_length=1 enforcement bubbles as isError via FastMCP."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=70,
            name="start_credential_rotation",
            arguments={
                "credential_id": str(uuid4()),
                "new_secret_ref": "",
            },
        )
    assert body["result"]["isError"] is True
