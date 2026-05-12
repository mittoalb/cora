"""Contract tests for the `register_dataset` and `get_dataset` MCP tools."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from tests.contract._mcp_helpers import open_session, parse_sse_data

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


def _register_args(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "32-ID FlyScan recon",
        "uri": "s3://aps-32id/runs/abc/recon.h5",
        "checksum_algorithm": "sha256",
        "checksum_value": _GOOD_SHA256,
        "byte_size": 1024,
        "media_type": "application/x-hdf5",
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_mcp_lists_register_dataset_and_get_dataset_tools() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "register_dataset" in tool_names
    assert "get_dataset" in tool_names


@pytest.mark.contract
def test_mcp_register_dataset_tool_succeeds_on_minimum_args() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "register_dataset",
                    "arguments": _register_args(),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_register_dataset_tool_succeeds_with_all_optional_refs() -> None:
    with TestClient(create_app()) as client:
        upstream_id = client.post(
            "/datasets",
            json={
                "name": "raw",
                "uri": "s3://b/k",
                "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
                "byte_size": 0,
                "format": {"media_type": "application/x-hdf5", "conforms_to": []},
            },
        ).json()["dataset_id"]
        subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "register_dataset",
                    "arguments": _register_args(
                        subject_id=subject_id,
                        derived_from=[upstream_id],
                        conforms_to=["https://manual.nexusformat.org/"],
                    ),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False


@pytest.mark.contract
def test_mcp_register_dataset_tool_returns_iserror_for_unknown_subject() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "register_dataset",
                    "arguments": _register_args(subject_id=str(uuid4())),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "subject_id" in body["result"]["content"][0]["text"]


@pytest.mark.contract
def test_mcp_get_dataset_tool_returns_dataset_after_registration() -> None:
    with TestClient(create_app()) as client:
        dataset_id = client.post(
            "/datasets",
            json={
                "name": "D",
                "uri": "s3://b/k",
                "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
                "byte_size": 0,
                "format": {"media_type": "application/x-hdf5", "conforms_to": []},
            },
        ).json()["dataset_id"]
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "get_dataset",
                    "arguments": {"dataset_id": dataset_id},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is False
    structured = body["result"]["structuredContent"]
    assert structured["id"] == dataset_id
    assert structured["status"] == "Registered"


@pytest.mark.contract
def test_mcp_get_dataset_tool_returns_iserror_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {
                    "name": "get_dataset",
                    "arguments": {"dataset_id": str(uuid4())},
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "not found" in body["result"]["content"][0]["text"].lower()
