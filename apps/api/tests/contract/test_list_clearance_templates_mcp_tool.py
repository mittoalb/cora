"""Contract tests for the `list_clearance_templates` MCP tool.

Pins tool registration on the MCP server, the input-schema cursor +
limit + facility_code + status + code optionality, the structured
output shape (`items` + `next_cursor`), cursor + filter pass-through to
the bound handler, and Authorize-Deny bubbling as `isError: true`.
"""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.safety.errors import UnauthorizedError
from cora.safety.features.list_clearance_templates.handler import (
    ClearanceTemplateListPage,
    ClearanceTemplateSummaryItem,
)
from cora.safety.features.list_clearance_templates.query import ListClearanceTemplates
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_list_clearance_templates_tool() -> None:
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
    assert "list_clearance_templates" in tool_names


@pytest.mark.contract
def test_mcp_list_clearance_templates_input_schema_pins_optional_fields() -> None:
    """Every advertised filter (cursor, limit, facility_code, status, code)
    is present in the input schema and none of them are required."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tools = {t["name"]: t for t in body["result"]["tools"]}
    schema = tools["list_clearance_templates"]["inputSchema"]
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    assert {"cursor", "limit", "facility_code", "status", "code"}.issubset(properties.keys())
    assert required.isdisjoint({"cursor", "limit", "facility_code", "status", "code"})


@pytest.mark.contract
def test_mcp_list_clearance_templates_tool_returns_empty_page_default() -> None:
    """In-memory app has no pool; tool returns empty items + null cursor."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "list_clearance_templates", "arguments": {}},
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    structured = result["structuredContent"]
    assert structured["items"] == []
    assert structured["next_cursor"] is None


@pytest.mark.contract
def test_mcp_list_clearance_templates_tool_accepts_combined_filters() -> None:
    """`facility_code` + `status` + `code` + `limit` together must parse
    cleanly even though the empty in-memory projection returns no rows."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "list_clearance_templates",
                    "arguments": {
                        "facility_code": "aps",
                        "status": "Active",
                        "code": "radiation-safety-form",
                        "limit": 25,
                    },
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["items"] == []


@pytest.mark.contract
def test_mcp_list_clearance_templates_tool_returns_iserror_on_invalid_status() -> None:
    """`Mystery` is NOT in the ClearanceTemplateStatusFilter Literal."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "list_clearance_templates",
                    "arguments": {"status": "Mystery"},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_list_clearance_templates_tool_rejects_limit_above_cap_as_iserror() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "list_clearance_templates",
                    "arguments": {"limit": 101},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_list_clearance_templates_tool_rejects_limit_below_one_as_iserror() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "list_clearance_templates",
                    "arguments": {"limit": 0},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_list_clearance_templates_tool_passes_cursor_and_filters_to_handler() -> None:
    """Swap the wired handler for a stub; verify the MCP tool forwards every
    advertised filter onto the `ListClearanceTemplates` query, returns the
    stub's items intact, and surfaces `next_cursor` in `structuredContent`."""
    captured: dict[str, Any] = {}
    template_id = uuid4()
    defined_at = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    stub_item = ClearanceTemplateSummaryItem(
        template_id=template_id,
        code="radiation-safety-form",
        title="Radiation Safety Form",
        facility_code="aps",
        version=1,
        status="Active",
        defined_at=defined_at,
    )
    stub_page = ClearanceTemplateListPage(items=[stub_item], next_cursor="opaque-next")

    async def _stub_handler(
        query: ListClearanceTemplates,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID,
    ) -> ClearanceTemplateListPage:
        captured["query"] = query
        captured["principal_id"] = principal_id
        captured["correlation_id"] = correlation_id
        captured["surface_id"] = surface_id
        return stub_page

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            list_clearance_templates=_stub_handler,
        )
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {
                    "name": "list_clearance_templates",
                    "arguments": {
                        "cursor": "opaque-prev",
                        "limit": 25,
                        "facility_code": "aps",
                        "status": "Active",
                        "code": "radiation-safety-form",
                    },
                },
            },
            headers=session_headers,
        )

    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    structured = result["structuredContent"]
    assert structured["next_cursor"] == "opaque-next"
    assert len(structured["items"]) == 1
    row = structured["items"][0]
    assert row["template_id"] == str(template_id)
    assert row["code"] == "radiation-safety-form"
    assert row["title"] == "Radiation Safety Form"
    assert row["facility_code"] == "aps"
    assert row["version"] == 1
    assert row["status"] == "Active"

    query = captured["query"]
    assert isinstance(query, ListClearanceTemplates)
    assert query.cursor == "opaque-prev"
    assert query.limit == 25
    assert query.facility_code == "aps"
    assert query.status == "Active"
    assert query.code == "radiation-safety-form"


@pytest.mark.contract
def test_mcp_list_clearance_templates_tool_authorize_deny_bubbles_as_iserror() -> None:
    """Replace the wired handler with one that raises `UnauthorizedError`,
    mirroring how the production `TrustAuthorize` would on a Deny. The MCP
    tool surfaces it as `isError: true` per the FastMCP contract."""

    async def _denying_handler(*_args: object, **_kwargs: object) -> ClearanceTemplateListPage:
        raise UnauthorizedError("denied for test")

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            list_clearance_templates=_denying_handler,
        )
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {"name": "list_clearance_templates", "arguments": {}},
            },
            headers=session_headers,
        )

    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
