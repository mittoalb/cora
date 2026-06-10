"""Contract tests for the `register_distribution` MCP tool.

## Scope

The TestClient app's cross-BC `SupplyLookup` adapter is the default
`AllSatisfiedSupplyLookup` stub (no postgres pool, no projection
worker), so the lookup-by-id branch returns None on every call. The
happy path (isError=False) is locked in
`tests/integration/test_register_distribution_handler_postgres.py`
where `PostgresSupplyLookup` against `proj_supply_summary` is wired
in. These contract tests pin the MCP wire shape:

  - Tool is listed by `tools/list`.
  - `tools/call` accepts the flat arg schema and returns isError=True
    with a Distribution-prefixed message when supply_id does not
    resolve (the universally-reachable error path under the test
    stub).
  - Unknown access_protocol enum value is rejected at the MCP arg
    schema before reaching the handler.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from tests.contract._mcp_helpers import open_session, parse_sse_data

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


def _register_dataset(client: TestClient) -> str:
    response = client.post(
        "/datasets",
        json={
            "name": "mcp-dataset",
            "uri": "s3://aps-32id/runs/abc/recon.h5",
            "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
            "byte_size": 1024,
            "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["dataset_id"]


def _register_args(
    *,
    dataset_id: str | None = None,
    supply_id: str | None = None,
    **overrides: object,
) -> dict[str, object]:
    base: dict[str, object] = {
        "dataset_id": dataset_id or str(uuid4()),
        "supply_id": supply_id or str(uuid4()),
        "uri": "s3://aps-32id/runs/abc/recon.h5",
        "checksum_algorithm": "sha256",
        "checksum_value": _GOOD_SHA256,
        "byte_size": 1024,
        "media_type": "application/x-hdf5",
        "access_protocol": "S3",
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_mcp_lists_register_distribution_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "register_distribution" in tool_names


@pytest.mark.contract
def test_mcp_register_distribution_tool_returns_iserror_for_unknown_dataset() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "register_distribution",
                    "arguments": _register_args(),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    # Default supply_lookup stub returns None for every id; dataset
    # pre-load also fails since the dataset_id is fresh. Either error
    # surfaces as isError=True with a 404-style message.
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_register_distribution_tool_returns_iserror_for_unknown_supply() -> None:
    """Cross-BC SupplyLookup returns None under the default test stub ->
    DistributionSupplyNotFoundError -> isError=True."""
    with TestClient(create_app()) as client:
        dataset_id = _register_dataset(client)
        unknown_supply = str(uuid4())
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "register_distribution",
                    "arguments": _register_args(dataset_id=dataset_id, supply_id=unknown_supply),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    text = body["result"]["content"][0]["text"]
    assert unknown_supply in text


@pytest.mark.contract
def test_mcp_register_distribution_tool_rejects_unknown_access_protocol() -> None:
    """Closed AccessProtocol enum: MCP arg schema rejects out-of-enum values."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "register_distribution",
                    "arguments": _register_args(access_protocol="FTP"),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
