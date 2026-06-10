"""Contract tests for the `get_clearance_template` MCP tool.

Pins tool registration on the MCP server, the input-schema `template_id`
requirement, the structured output shape (`ClearanceTemplateOutput`),
the `None`-result -> `isError: true` + diagnostic text mapping (FastMCP
wraps the raised `ValueError` per the same idiom REST surfaces as 404),
and Authorize-Deny bubbling as `isError: true` (mirrors how the
production `TrustAuthorize` would on a Deny).
"""

from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.safety.aggregates.clearance_template import ClearanceTemplate
from cora.safety.errors import UnauthorizedError
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_template_via_tool(
    client: TestClient,
    session_headers: dict[str, str],
    *,
    code: str = "radiation-safety-form",
    title: str = "Radiation Safety Form",
    facility_code: str = "cora",
) -> UUID:
    """Seed a ClearanceTemplate via the sibling `define_clearance_template`
    MCP tool. Same in-process in-memory store backs every tool via the
    lifespan-built Kernel."""
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 100,
            "method": "tools/call",
            "params": {
                "name": "define_clearance_template",
                "arguments": {
                    "code": code,
                    "title": title,
                    "facility_code": facility_code,
                },
            },
        },
        headers=session_headers,
    )
    assert response.status_code == 200, response.text
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False, body
    return UUID(body["result"]["structuredContent"]["template_id"])


@pytest.mark.contract
def test_mcp_lists_get_clearance_template_tool() -> None:
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
    assert "get_clearance_template" in tool_names


@pytest.mark.contract
def test_mcp_get_clearance_template_input_schema_requires_template_id() -> None:
    """The lone argument `template_id` must be advertised as required."""
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
    schema = tools["get_clearance_template"]["inputSchema"]
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    assert "template_id" in properties
    assert "template_id" in required


@pytest.mark.contract
def test_mcp_get_clearance_template_tool_returns_structured_state_on_hit() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        template_id = _define_template_via_tool(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_clearance_template",
                    "arguments": {"template_id": str(template_id)},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    structured = result["structuredContent"]
    assert structured["id"] == str(template_id)
    assert structured["code"] == "radiation-safety-form"
    assert structured["title"] == "Radiation Safety Form"
    assert structured["facility_code"] == "cora"
    assert structured["version"] == 1
    assert structured["status"] == "Draft"
    assert structured["supersedes_template_id"] is None
    assert structured["external_ref"] is None
    UUID(structured["defined_by"])
    assert isinstance(structured["defined_at"], str)


@pytest.mark.contract
def test_mcp_get_clearance_template_tool_returns_iserror_on_miss() -> None:
    """Handler returns None for an unknown template_id; the tool raises
    ValueError, which FastMCP wraps as `isError: true` + a text
    diagnostic (matches REST 404 semantically)."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_clearance_template",
                    "arguments": {"template_id": str(uuid4())},
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is True
    assert "not found" in result["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_get_clearance_template_tool_authorize_deny_bubbles_as_iserror() -> None:
    """Replace the wired handler with one that raises `UnauthorizedError`,
    mirroring how the production `TrustAuthorize` would on a Deny. The MCP
    tool surfaces it as `isError: true` per the FastMCP contract."""

    async def _denying_handler(*_args: object, **_kwargs: object) -> ClearanceTemplate | None:
        raise UnauthorizedError("denied for test")

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            get_clearance_template=_denying_handler,
        )
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "get_clearance_template",
                    "arguments": {"template_id": str(uuid4())},
                },
            },
            headers=session_headers,
        )

    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
