"""Contract tests for the ``record_attestation`` MCP tool.

## Scope

The TestClient app does not pre-seed any Distribution. We pin:

  - Tool is listed by ``tools/list``.
  - ``tools/call`` rejects unknown kind / outcome values at the MCP
    arg schema before reaching the handler.
  - ``tools/call`` returns isError=True with a 404-style message when
    the dataset_id never resolves.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_GOOD_SHA = "a" * 64


def _record_args(
    *,
    dataset_id: str | None = None,
    distribution_id: str | None = None,
    **overrides: object,
) -> dict[str, object]:
    base: dict[str, object] = {
        "dataset_id": dataset_id or str(uuid4()),
        "distribution_id": distribution_id or str(uuid4()),
        "kind": "ChecksumVerified",
        "outcome": "Match",
        "evidence_expected_checksum": _GOOD_SHA,
        "evidence_computed_checksum": _GOOD_SHA,
        "evidence_algorithm": "sha256",
        "evidence_verifier_supply_id": str(uuid4()),
        "evidence_verifier_kind": "HttpRangeChecksum",
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_mcp_lists_record_attestation_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "record_attestation" in tool_names


@pytest.mark.contract
def test_mcp_record_attestation_returns_iserror_for_unknown_dataset() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "record_attestation",
                    "arguments": _record_args(),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_record_attestation_rejects_unknown_kind() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "record_attestation",
                    "arguments": _record_args(kind="HashChecked"),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_record_attestation_rejects_unknown_outcome() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "record_attestation",
                    "arguments": _record_args(outcome="Pending"),
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
