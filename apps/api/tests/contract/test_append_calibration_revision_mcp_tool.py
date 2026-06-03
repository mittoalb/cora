"""Contract tests for the `append_calibration_revision` MCP tool."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _define_args() -> dict[str, Any]:
    return {
        "target_id": str(uuid4()),
        "quantity": "rotation_center",
        "operating_point": {"energy": 25.0, "optics_config": "5x"},
    }


def _revision_args(*, calibration_id: str, **overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "calibration_id": calibration_id,
        "value": {"center": 1024.5},
        "status": "Provisional",
        "source": {"kind": "Measured", "procedure_id": str(uuid4())},
    }
    base.update(overrides)
    return base


def _seed_calibration(client: TestClient, session_headers: dict[str, str]) -> str:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "define_calibration", "arguments": _define_args()},
        },
        headers=session_headers,
    )
    assert response.status_code == 200, response.text
    body = parse_sse_data(response.text)
    return str(body["result"]["structuredContent"]["calibration_id"])


@pytest.mark.contract
def test_mcp_lists_append_calibration_revision_tool() -> None:
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
    assert "append_calibration_revision" in tool_names


@pytest.mark.contract
def test_mcp_append_calibration_revision_tool_returns_structured_revision_id() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        cid = _seed_calibration(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "append_calibration_revision",
                    "arguments": _revision_args(calibration_id=cid),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert "revision_id" in result["structuredContent"]
    UUID(result["structuredContent"]["revision_id"])


@pytest.mark.contract
def test_mcp_append_calibration_revision_tool_returns_iserror_on_unknown_source_kind() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        cid = _seed_calibration(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "append_calibration_revision",
                    "arguments": _revision_args(
                        calibration_id=cid,
                        source={"kind": "Inferred", "procedure_id": str(uuid4())},
                    ),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_append_calibration_revision_tool_returns_iserror_on_missing_value_key() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        cid = _seed_calibration(client, session_headers)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "append_calibration_revision",
                    "arguments": _revision_args(
                        calibration_id=cid,
                        value={"uncertainty": 0.3},  # missing center
                    ),
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_append_calibration_revision_tool_rejects_missing_required_argument() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "append_calibration_revision",
                    "arguments": {"calibration_id": str(uuid4())},  # missing the rest
                },
            },
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
