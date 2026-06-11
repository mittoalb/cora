"""Contract tests for the `register_edition` MCP tool."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _register_args(
    *,
    dataset_ids: list[str] | None = None,
    **overrides: object,
) -> dict[str, object]:
    base: dict[str, object] = {
        "kind": "ROCrate",
        "title": "MCP Edition",
        "dataset_ids": [str(uuid4())] if dataset_ids is None else dataset_ids,
        "creators": [
            {"actor_id": str(uuid4()), "affiliation": "ANL"},
        ],
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_mcp_lists_register_edition_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "register_edition" in tool_names


@pytest.mark.contract
def test_mcp_register_edition_tool_returns_iserror_for_unknown_dataset() -> None:
    """Missing member Dataset -> DatasetNotFoundError -> isError=True."""
    missing = str(uuid4())
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "register_edition",
                    "arguments": _register_args(dataset_ids=[missing]),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    text = body["result"]["content"][0]["text"]
    assert missing in text


@pytest.mark.contract
def test_mcp_register_edition_tool_rejects_unknown_kind() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "register_edition",
                    "arguments": _register_args(kind="JunkKind"),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
