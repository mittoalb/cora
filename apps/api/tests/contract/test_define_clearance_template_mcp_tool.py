"""Contract tests for the `define_clearance_template` MCP tool.

Pins tool registration on the MCP server, the input schema's required
versus optional fields (`code` / `title` / `facility_code` required;
`supersedes_template_id` / `external_ref` optional), the happy-path
structured output shape (`template_id` as a UUID), and the error-path
bubbling per FastMCP convention (Pydantic-layer rejection on missing
required argument and decider-layer rejection on an unseeded facility
slug both surface as `isError: true`).
"""

from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_FACILITY_CODE = "cora"


def _args(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "code": "radiation-safety-form",
        "title": "Radiation Safety Form",
        "facility_code": _FACILITY_CODE,
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_mcp_lists_define_clearance_template_tool() -> None:
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
    assert "define_clearance_template" in tool_names


@pytest.mark.contract
def test_mcp_define_clearance_template_input_schema_pins_required_and_optional_fields() -> None:
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
    schema = tools["define_clearance_template"]["inputSchema"]
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    assert {"code", "title", "facility_code"}.issubset(properties.keys())
    assert "external_ref" in properties
    assert {"code", "title", "facility_code"}.issubset(required)
    assert "external_ref" not in required


@pytest.mark.contract
def test_mcp_define_clearance_template_tool_returns_structured_template_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "define_clearance_template",
                    "arguments": _args(),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert "template_id" in result["structuredContent"]
    UUID(result["structuredContent"]["template_id"])


@pytest.mark.contract
def test_mcp_define_clearance_template_tool_rejects_missing_required_argument() -> None:
    """Pydantic-layer rejection (facility_code missing) bubbles as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        args = _args()
        del args["facility_code"]
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "define_clearance_template",
                    "arguments": args,
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_define_clearance_template_tool_rejects_malformed_facility_code() -> None:
    """Pydantic regex on facility_code rejects uppercase/whitespace input as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "define_clearance_template",
                    "arguments": _args(facility_code="INVALID UPPER"),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_define_clearance_template_tool_returns_iserror_on_unseeded_facility() -> None:
    """Cross-BC ClearanceTemplateFacilityNotFoundError surfaces through FastMCP as isError: true."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "define_clearance_template",
                    "arguments": _args(facility_code="unseeded"),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
