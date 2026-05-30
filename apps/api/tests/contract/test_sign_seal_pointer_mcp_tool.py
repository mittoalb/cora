"""Contract tests for the `sign_seal_pointer` MCP tool.

Pin tool listing, structured-content shape on the happy path (via
handler override), and the `isError: true` mappings for the decider-
layer FSM rejection (Republishing), the sequence-regression branch,
the unknown-facility branch, plus Pydantic-layer rejection (missing
`new_head_hash`, missing `new_sequence_number`, empty
`new_head_hash`).
"""

from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.seal import (
    SealCannotSignError,
    SealNotFoundError,
    SealSequenceNumberRegressionError,
    SealStatus,
)
from cora.federation.features.sign_seal_pointer.handler import Handler
from tests.contract._mcp_helpers import open_session, parse_sse_data

_FACILITY_ID = "aps-2bm"
_NEW_HEAD_HASH = "b" * 64


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
    object.__setattr__(state, "sign_seal_pointer", handler)


@pytest.mark.contract
def test_mcp_lists_sign_seal_pointer_tool() -> None:
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
    assert "sign_seal_pointer" in tool_names


@pytest.mark.contract
def test_mcp_sign_seal_pointer_tool_returns_structured_facility_id() -> None:
    """Happy path via handler override: tool returns structured facility_id and
    new_sequence_number (matches REST 204 + path-id contract)."""
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
            request_id=20,
            name="sign_seal_pointer",
            arguments={
                "facility_id": _FACILITY_ID,
                "new_head_hash": _NEW_HEAD_HASH,
                "new_sequence_number": 1,
            },
        )
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["facility_id"] == _FACILITY_ID
    assert result["structuredContent"]["new_sequence_number"] == 1


@pytest.mark.contract
def test_mcp_sign_seal_pointer_tool_returns_iserror_on_republishing_seal() -> None:
    """Decider-layer FSM rejection (Republishing != Live) surfaces through
    FastMCP as isError: true."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealCannotSignError(_FACILITY_ID, SealStatus.REPUBLISHING)

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=30,
            name="sign_seal_pointer",
            arguments={
                "facility_id": _FACILITY_ID,
                "new_head_hash": _NEW_HEAD_HASH,
                "new_sequence_number": 2,
            },
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_sign_seal_pointer_tool_returns_iserror_on_sequence_regression() -> None:
    """Decider-layer sequence-regression rejection surfaces through FastMCP."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealSequenceNumberRegressionError(
            facility_id=_FACILITY_ID,
            prior_sequence_number=5,
            proposed_sequence_number=5,
        )

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=31,
            name="sign_seal_pointer",
            arguments={
                "facility_id": _FACILITY_ID,
                "new_head_hash": _NEW_HEAD_HASH,
                "new_sequence_number": 5,
            },
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_sign_seal_pointer_tool_returns_iserror_on_unknown_facility() -> None:
    """A handler raising SealNotFoundError surfaces through FastMCP."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealNotFoundError("unknown-facility")

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=40,
            name="sign_seal_pointer",
            arguments={
                "facility_id": _FACILITY_ID,
                "new_head_hash": _NEW_HEAD_HASH,
                "new_sequence_number": 1,
            },
        )
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_sign_seal_pointer_tool_rejects_missing_facility_id() -> None:
    """Pydantic-layer rejection (missing facility_id) bubbles as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=60,
            name="sign_seal_pointer",
            arguments={
                "new_head_hash": _NEW_HEAD_HASH,
                "new_sequence_number": 1,
            },
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_sign_seal_pointer_tool_rejects_missing_new_head_hash() -> None:
    """Pydantic-layer rejection (missing new_head_hash) bubbles as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=61,
            name="sign_seal_pointer",
            arguments={
                "facility_id": _FACILITY_ID,
                "new_sequence_number": 1,
            },
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_sign_seal_pointer_tool_rejects_missing_new_sequence_number() -> None:
    """Pydantic-layer rejection (missing new_sequence_number) bubbles as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=62,
            name="sign_seal_pointer",
            arguments={
                "facility_id": _FACILITY_ID,
                "new_head_hash": _NEW_HEAD_HASH,
            },
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_sign_seal_pointer_tool_rejects_empty_new_head_hash() -> None:
    """Pydantic min_length=1 enforcement bubbles as isError via FastMCP."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=70,
            name="sign_seal_pointer",
            arguments={
                "facility_id": _FACILITY_ID,
                "new_head_hash": "",
                "new_sequence_number": 1,
            },
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_sign_seal_pointer_tool_rejects_zero_sequence_number() -> None:
    """Pydantic ge=1 enforcement bubbles as isError via FastMCP."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=71,
            name="sign_seal_pointer",
            arguments={
                "facility_id": _FACILITY_ID,
                "new_head_hash": _NEW_HEAD_HASH,
                "new_sequence_number": 0,
            },
        )
    assert body["result"]["isError"] is True
