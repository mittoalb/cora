"""Contract tests for the `define_calibration` MCP tool."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _args(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "principal_id": str(uuid4()),
        "subsystem_or_asset_id": str(uuid4()),
        "quantity": "rotation_center",
        "operating_point": {"energy_keV": 25.0, "optics_config": "5x"},
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_mcp_lists_define_calibration_tool() -> None:
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
    assert "define_calibration" in tool_names


@pytest.mark.contract
def test_mcp_define_calibration_tool_returns_structured_calibration_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "define_calibration", "arguments": _args()},
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert "calibration_id" in result["structuredContent"]
    UUID(result["structuredContent"]["calibration_id"])


@pytest.mark.contract
def test_mcp_define_calibration_tool_returns_iserror_on_unknown_quantity() -> None:
    """Closed CalibrationQuantity enum at the wire layer; pydantic rejection
    surfaces as isError: true through FastMCP."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "define_calibration",
                    "arguments": _args(quantity="rotation_centre"),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_define_calibration_iserror_on_missing_required_op_point_key() -> None:
    """STRICT schema validation; missing required key bubbles via FastMCP."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "define_calibration",
                    "arguments": _args(operating_point={"energy_keV": 25.0}),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_define_calibration_tool_rejects_missing_required_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "define_calibration",
                    "arguments": {"quantity": "rotation_center"},  # missing the rest
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
