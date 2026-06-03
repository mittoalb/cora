"""Contract tests for the `register_procedure_from_recipe` MCP tool."""

from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _call_tool(
    client: TestClient,
    session_headers: dict[str, str],
    tool: str,
    arguments: dict[str, Any],
    request_id: int,
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        },
        headers=session_headers,
    )
    return parse_sse_data(response.text)["result"]


def _capability_args() -> dict[str, Any]:
    return {
        "code": "cora.capability.mcp_rfr",
        "name": "MCPRFR",
        "required_affordances": [],
        "executor_shapes": ["Method", "Procedure"],
    }


def _recipe_args(capability_id: str) -> dict[str, Any]:
    return {
        "name": "R",
        "capability_id": capability_id,
        "steps": {
            "steps": [{"kind": "setpoint", "address": "dev:x", "value": 1.0, "verify": False}]
        },
    }


@pytest.mark.contract
def test_mcp_lists_register_procedure_from_recipe_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "register_procedure_from_recipe" in tool_names


@pytest.mark.contract
def test_mcp_register_procedure_from_recipe_returns_structured_procedure_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        cap = _call_tool(client, session_headers, "define_capability", _capability_args(), 2)
        capability_id = cap["structuredContent"]["capability_id"]
        recipe = _call_tool(
            client, session_headers, "define_recipe", _recipe_args(capability_id), 3
        )
        recipe_id = recipe["structuredContent"]["recipe_id"]
        result = _call_tool(
            client,
            session_headers,
            "register_procedure_from_recipe",
            {"name": "P", "kind": "bakeout", "recipe_id": recipe_id},
            4,
        )
    assert result["isError"] is False
    assert "procedure_id" in result["structuredContent"]
    UUID(result["structuredContent"]["procedure_id"])
