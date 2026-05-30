"""Contract tests for the `complete_seal_republishing` MCP tool.

Pin tool listing, structured-content shape on the happy path (via
handler override), and the `isError: true` mappings for the decider-
layer FSM rejection plus the unknown-Seal branch plus the
sequence-regression and pairing-imbalance failure modes.
"""

from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.seal import (
    SealCannotCompleteRepublishingError,
    SealNotFoundError,
    SealSequenceNumberRegressionError,
    SealStatus,
)
from cora.federation.features.complete_seal_republishing.handler import Handler
from tests.contract._mcp_helpers import open_session, parse_sse_data

_FACILITY_ID = "aps-2bm"


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
    object.__setattr__(state, "complete_seal_republishing", handler)


@pytest.mark.contract
def test_mcp_lists_complete_seal_republishing_tool() -> None:
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
    assert "complete_seal_republishing" in tool_names


@pytest.mark.contract
def test_mcp_complete_seal_republishing_tool_returns_structured_facility_id() -> None:
    """Happy path via handler override: tool returns structured facility_id
    (matches REST 204 + path-id contract)."""
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
            name="complete_seal_republishing",
            arguments={
                "facility_id": _FACILITY_ID,
                "new_head_hash": "b" * 64,
                "new_sequence_number": 1,
            },
        )
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["facility_id"] == _FACILITY_ID


@pytest.mark.contract
def test_mcp_complete_seal_republishing_tool_accepts_omitted_pair_fields() -> None:
    """`new_head_hash` and `new_sequence_number` are optional; omitting
    them succeeds at the MCP edge (the handler decides the rest)."""
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
            name="complete_seal_republishing",
            arguments={"facility_id": _FACILITY_ID},
        )
    assert body["result"]["isError"] is False, body


@pytest.mark.contract
def test_mcp_complete_seal_republishing_tool_returns_iserror_when_live() -> None:
    """Decider-layer FSM rejection (Live != Republishing) surfaces through
    FastMCP as isError: true."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealCannotCompleteRepublishingError(
            facility_id=_FACILITY_ID,
            current_status=SealStatus.LIVE,
        )

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=30,
            name="complete_seal_republishing",
            arguments={"facility_id": _FACILITY_ID},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_complete_seal_republishing_tool_returns_iserror_on_unknown_seal() -> None:
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
            name="complete_seal_republishing",
            arguments={"facility_id": "unknown-facility"},
        )
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_complete_seal_republishing_tool_returns_iserror_on_sequence_regression() -> None:
    """SealSequenceNumberRegressionError surfaces through FastMCP."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealSequenceNumberRegressionError(
            facility_id=_FACILITY_ID,
            prior_sequence_number=5,
            proposed_sequence_number=3,
        )

    with TestClient(app) as client:
        _override_handler(app, fake_handler)
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=50,
            name="complete_seal_republishing",
            arguments={
                "facility_id": _FACILITY_ID,
                "new_head_hash": "b" * 64,
                "new_sequence_number": 3,
            },
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_complete_seal_republishing_tool_rejects_missing_facility_id() -> None:
    """Pydantic-layer rejection (missing facility_id) bubbles as isError."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=60,
            name="complete_seal_republishing",
            arguments={},
        )
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_complete_seal_republishing_tool_rejects_non_integer_sequence() -> None:
    """Pydantic integer coercion failure surfaces as isError via FastMCP."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _call_tool(
            client,
            headers=headers,
            request_id=70,
            name="complete_seal_republishing",
            arguments={
                "facility_id": _FACILITY_ID,
                "new_head_hash": "b" * 64,
                "new_sequence_number": "not-an-int",
            },
        )
    assert body["result"]["isError"] is True
