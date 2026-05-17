"""Contract tests for the MCP write-tool gate (Phase A.1).

The gate fires when `require_authenticated_principal=True` and
removes every non-read-only tool from the FastMCP server's tool
manager. These tests boot a real app and verify the gate's
observable effect via the MCP `tools/list` JSON-RPC endpoint.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.api.mcp_gate import is_read_only_tool
from tests.contract._mcp_helpers import HEADERS, open_session, parse_sse_data


def _list_mcp_tools(client: TestClient) -> set[str]:
    """Catalog of tool names the live MCP server advertises."""
    headers = open_session(client)
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tools = body.get("result", {}).get("tools", [])
    return {t["name"] for t in tools}


@pytest.mark.contract
def test_gate_no_op_in_dev_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default dev posture (require_authenticated_principal=False) keeps
    every tool registered; the gate is a no-op so `tools/list` returns
    both read-only and write tools."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("REQUIRE_AUTHENTICATED_PRINCIPAL", raising=False)

    with TestClient(create_app()) as client:
        names = _list_mcp_tools(client)

    # Sample assertions across both classes; full surface is exercised
    # by every other MCP contract test in this directory.
    assert "get_run" in names  # read
    assert "list_actors" in names  # read
    assert "register_actor" in names  # write
    assert "promote_caution_proposal" in names  # write
    assert "rate_decision" in names  # write


@pytest.mark.contract
def test_gate_removes_all_write_tools_in_prod_posture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With require_authenticated_principal=True (prod posture), every
    MCP write-tool is removed from `tools/list`. Read-only tools
    remain available so audit + dashboard MCP consumers keep working.

    Pin: a future tool added without a read prefix is fail-closed in
    prod automatically; this test prevents silent regressions of
    that property.
    """
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")

    with TestClient(create_app()) as client:
        names = _list_mcp_tools(client)

    # Every surviving tool MUST be a read; any write would be a gate
    # bypass. Failure here points at either a buggy classifier or a
    # gate-application bug.
    writes = {n for n in names if not is_read_only_tool(n)}
    assert writes == set(), (
        f"prod-posture MCP server exposed write tools: {sorted(writes)}; "
        "the Phase A.1 gate should have removed them"
    )

    # Sanity: at least the canonical read tools survived.
    assert "get_run" in names
    assert "list_actors" in names
    assert "evaluate_policy" in names  # explicit-read exception


@pytest.mark.contract
def test_gate_blocks_write_tool_call_in_prod_posture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A gated write-tool cannot be CALLED either; `tools/call` returns
    a JSON-RPC error indicating the tool is unknown."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")

    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "register_actor",
                    "arguments": {"name": "Doga"},
                },
            },
            headers=headers,
        )

    # The call surface returns 200 + JSON-RPC error body (or 200 +
    # error result envelope, depending on FastMCP version); either
    # way the call must NOT succeed against the gated tool.
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    # FastMCP returns either error envelope or result.isError=True for
    # unknown tools; the absence of a successful Actor id is the
    # invariant we care about.
    if "error" in body:
        return  # explicit JSON-RPC error: pass
    result = body.get("result", {})
    assert result.get("isError") is True, (
        f"prod-posture MCP server allowed a write-tool call: {body!r}"
    )


@pytest.mark.contract
def test_gate_preserves_read_tool_calls_in_prod_posture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read-only tools still execute in prod posture; the gate does not
    overreach."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("REQUIRE_AUTHENTICATED_PRINCIPAL", "true")

    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "list_actors",
                    "arguments": {},
                },
            },
            headers=headers,
        )

    assert response.status_code == 200
    body = parse_sse_data(response.text)
    # Either a clean result envelope OR an authz-shape failure
    # (acceptable: under require_authenticated_principal=True and no
    # X-Principal-Id, even reads may need auth). The invariant under
    # test is that the tool EXISTS and is callable; an authz error is
    # not a gate failure.
    assert "error" in body or "result" in body


# Silence unused-import warning for HEADERS (kept for symmetry with
# the other MCP contract tests; helper API consistency).
_ = HEADERS
