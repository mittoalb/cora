"""Contract tests for the `start_seal_republishing` MCP tool.

Pin tool listing, structured-content shape on the happy path (via
handler override), and the `isError: true` mappings for the decider-
layer FSM rejection plus the uninitialized-Seal branch plus
Pydantic-layer rejection (missing `facility_code`, empty `facility_code`).
"""

from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.seal import (
    SealCannotStartRepublishingError,
    SealNotFoundError,
    SealStatus,
)
from cora.federation.features.start_seal_republishing.handler import Handler
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
    object.__setattr__(state, "start_seal_republishing", handler)


@pytest.mark.contract
def test_mcp_lists_start_seal_republishing_tool() -> None:
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
    assert "start_seal_republishing" in tool_names


@pytest.mark.contract
def test_mcp_start_seal_republishing_tool_returns_structured_facility_code() -> None:
    """Happy path via handler override: tool returns structured facility_code
    (matches REST 204 + path-id contract)."""
    app = create_app()
    facility_code = "aps-2bm"

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
            name="start_seal_republishing",
            arguments={
                "facility_code": facility_code,
                "reason": "root rotation drill",
            },
        )
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["facility_code"] == facility_code


@pytest.mark.contract
def test_mcp_start_seal_republishing_tool_accepts_omitted_reason() -> None:
    """`reason` is optional; omitting it succeeds."""
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
            name="start_seal_republishing",
            arguments={"facility_code": "aps-2bm"},
        )
    assert body["result"]["isError"] is False, body


@pytest.mark.contract
def test_mcp_start_seal_republishing_tool_returns_iserror_on_republishing_seal() -> None:
    """Decider-layer FSM rejection (Republishing != Live) surfaces through
    FastMCP as isError: true."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealCannotStartRepublishingError("aps-2bm", SealStatus.REPUBLISHING)

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=30,
            name="start_seal_republishing",
            arguments={"facility_code": "aps-2bm"},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_start_seal_republishing_tool_returns_iserror_on_uninitialized_seal() -> None:
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
            request_id=40,
            name="start_seal_republishing",
            arguments={"facility_code": "aps-2bm"},
        )
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_start_seal_republishing_tool_rejects_missing_facility_code() -> None:
    """Pydantic-layer rejection (missing facility_code) bubbles as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=60,
            name="start_seal_republishing",
            arguments={"reason": "root rotation drill"},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_start_seal_republishing_tool_rejects_empty_facility_code() -> None:
    """Pydantic min_length=1 enforcement bubbles as isError via FastMCP."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=70,
            name="start_seal_republishing",
            arguments={"facility_code": ""},
        )
    assert body["result"]["isError"] is True
