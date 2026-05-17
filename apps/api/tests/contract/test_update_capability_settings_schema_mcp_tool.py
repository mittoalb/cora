"""Contract tests for the `update_capability_settings_schema` MCP tool."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _define_capability_via_tool(
    client: TestClient, headers: dict[str, str], name: str = "Tomography"
) -> UUID:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "define_capability",
                "arguments": {"name": name},
            },
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    return UUID(body["result"]["structuredContent"]["capability_id"])


@pytest.mark.contract
def test_mcp_lists_update_capability_settings_schema_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "update_capability_settings_schema" in tool_names


@pytest.mark.contract
def test_mcp_update_capability_settings_schema_tool_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        capability_id = _define_capability_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "update_capability_settings_schema",
                    "arguments": {
                        "capability_id": str(capability_id),
                        "settings_schema": {
                            "$schema": _DRAFT,
                            "type": "object",
                            "properties": {
                                "energy": {
                                    "type": "number",
                                    "minimum": 5,
                                    "unit": {"system": "udunits", "code": "keV"},
                                }
                            },
                        },
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_update_capability_settings_schema_tool_accepts_null_to_clear() -> None:
    """Passing settings_schema=None clears any prior schema declaration."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        capability_id = _define_capability_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "update_capability_settings_schema",
                    "arguments": {
                        "capability_id": str(capability_id),
                        "settings_schema": None,
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_update_capability_settings_schema_iserror_for_unknown_capability() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "update_capability_settings_schema",
                    "arguments": {
                        "capability_id": str(uuid4()),
                        "settings_schema": {
                            "$schema": _DRAFT,
                            "type": "object",
                        },
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()


@pytest.mark.contract
def test_mcp_update_capability_settings_schema_tool_returns_iserror_on_invalid_schema() -> None:
    """Schema without the required $schema key trips the validator
    (InvalidCapabilitySettingsSchemaError -> isError: true)."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        capability_id = _define_capability_via_tool(client, headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "update_capability_settings_schema",
                    "arguments": {
                        "capability_id": str(capability_id),
                        "settings_schema": {"type": "object"},  # no $schema
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
