"""Differential REST↔MCP test for the `register_actor` command.

Both surfaces expose the same logical operation through different
adapter code:

  - REST: POST /actors  with Pydantic-validated body, returns 201/4xx
  - MCP:  tools/call register_actor with MCP-derived JSON schema,
          returns `result.isError = false|true`

This file dispatches each input case through BOTH surfaces and
asserts wire-level parity:

  - same input → success on both OR error on both (no divergence
    where one surface accepts what the other rejects).
  - on success, both surfaces return a valid actor UUID.

The principal_id differs by design (REST: default test principal;
MCP: SYSTEM_PRINCIPAL_ID), and event-store-level differential checks
(payload deep-equality modulo metadata) are deferred to a later
iteration — this file pins the validation-parity invariant first.

Pattern source: McKeeman 1998 *differential testing*; canonical use
for compiler/SSL-validator/file-system equivalence testing. See
[[project-testing-techniques-research]] Corpus 3 for the survey.

Part of the testing-techniques rollout. First pass — extend to
additional commands by parameterising the dispatch helpers.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _rest_call(client: TestClient, arguments: dict[str, Any]) -> tuple[bool, int, dict[str, Any]]:
    """Dispatch `register_actor` via REST. Returns (success, status, body)."""
    response = client.post("/actors", json=arguments)
    success = 200 <= response.status_code < 300
    return success, response.status_code, response.json()


def _mcp_call(
    client: TestClient, headers: dict[str, str], arguments: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    """Dispatch `register_actor` via MCP. Returns (success, result_dict).

    Success = JSON-RPC envelope present and `result.isError = false`.
    For FastMCP schema-validation failures, the envelope has `error`
    instead of `result.isError`; we treat any of those as failure.
    """
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {"name": "register_actor", "arguments": arguments},
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    result = body.get("result", {})
    # Either a JSON-RPC `error` envelope OR `result.isError=true` is failure.
    success = "error" not in body and not result.get("isError", True)
    return success, body


# Each case: (label, arguments, expected_success).
# Inputs span happy path + every validator path documented in the
# REST + MCP schemas: min_length, max_length, closed-set discriminator,
# domain-layer guard (kind=agent). The expectation is OUTCOME (success
# vs error), not specific error text — error text differs by surface
# even when the underlying rejection is the same.
_CASES: list[tuple[str, dict[str, Any], bool]] = [
    ("happy_human", {"name": "Doga"}, True),
    ("happy_service_account", {"name": "ci-bot", "kind": "service_account"}, True),
    ("empty_name", {"name": ""}, False),
    ("overlong_name", {"name": "x" * 201}, False),
    ("kind_agent_rejected", {"name": "agent-attempt", "kind": "agent"}, False),
    ("kind_unknown", {"name": "doga", "kind": "robot"}, False),
    ("name_missing", {}, False),
]


@pytest.mark.contract
@pytest.mark.parametrize("label,arguments,expected_success", _CASES, ids=[c[0] for c in _CASES])
def test_register_actor_rest_and_mcp_agree_on_outcome(
    label: str, arguments: dict[str, Any], expected_success: bool
) -> None:
    """Both surfaces succeed OR both fail, on the same input."""
    with TestClient(create_app()) as client:
        rest_success, rest_status, rest_body = _rest_call(client, arguments)
        mcp_headers = open_session(client)
        mcp_success, mcp_body = _mcp_call(client, mcp_headers, arguments)

    assert rest_success == expected_success, (
        f"[{label}] REST expected success={expected_success}, "
        f"got status={rest_status} body={rest_body!r}"
    )
    assert mcp_success == expected_success, (
        f"[{label}] MCP expected success={expected_success}, got body={mcp_body!r}"
    )
    assert rest_success == mcp_success, (
        f"[{label}] DIFFERENTIAL: REST success={rest_success} but MCP success={mcp_success}\n"
        f"  REST: status={rest_status} body={rest_body!r}\n"
        f"  MCP:  body={mcp_body!r}"
    )

    # On success, both surfaces return a UUID-shaped actor identifier.
    if rest_success:
        assert "actor_id" in rest_body, (
            f"[{label}] REST success body missing actor_id: {rest_body!r}"
        )
        mcp_actor_id = mcp_body.get("result", {}).get("structuredContent", {}).get("actor_id")
        assert mcp_actor_id is not None, (
            f"[{label}] MCP success body missing structuredContent.actor_id: {mcp_body!r}"
        )
