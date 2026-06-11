"""Contract tests for the `remove_dataset_from_edition` MCP tool."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from tests.contract._mcp_helpers import open_session, parse_sse_data

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


def _register_dataset(client: TestClient, *, name: str = "ds") -> str:
    response = client.post(
        "/datasets",
        json={
            "name": name,
            "uri": f"s3://b/{name}",
            "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
            "byte_size": 1024,
            "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["dataset_id"]


def _register_edition(client: TestClient, *, dataset_ids: list[str]) -> str:
    response = client.post(
        "/editions",
        json={
            "kind": "ROCrate",
            "title": "MCP Edition",
            "dataset_ids": dataset_ids,
            "creators": [
                {"actor_id": str(uuid4()), "affiliation": "ANL"},
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["edition_id"]


@pytest.mark.contract
def test_mcp_lists_remove_dataset_from_edition_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "remove_dataset_from_edition" in tool_names


@pytest.mark.contract
def test_mcp_remove_dataset_from_edition_tool_returns_iserror_for_unknown_edition() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "remove_dataset_from_edition",
                    "arguments": {
                        "edition_id": str(uuid4()),
                        "dataset_id": str(uuid4()),
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_remove_dataset_from_edition_tool_succeeds_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        first = _register_dataset(client, name="first")
        second = _register_dataset(client, name="second")
        edition_id = _register_edition(client, dataset_ids=[first, second])
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "remove_dataset_from_edition",
                    "arguments": {
                        "edition_id": edition_id,
                        "dataset_id": first,
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"].get("isError") is not True, body
    structured = body["result"]["structuredContent"]
    assert structured["edition_id"] == edition_id
    assert structured["dataset_id"] == first
