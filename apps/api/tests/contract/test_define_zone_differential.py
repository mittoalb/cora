"""Differential REST↔MCP test for the `define_zone` command.

Proves the pattern from `test_register_actor_differential.py` scales
to a second command. The two surfaces:

  - REST: POST /zones  with Pydantic body
  - MCP:  tools/call define_zone with MCP-derived schema

Asserts outcome parity (success vs error) across the validation
surface that both schemas declare (min_length, max_length, missing).

See [[project-testing-techniques-research]] and the register-actor
sibling file for the broader rationale. Part of the testing-techniques
rollout.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


def _rest_call(client: TestClient, arguments: dict[str, Any]) -> tuple[bool, int, dict[str, Any]]:
    response = client.post("/zones", json=arguments)
    success = 200 <= response.status_code < 300
    return success, response.status_code, response.json()


def _mcp_call(
    client: TestClient, headers: dict[str, str], arguments: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {"name": "define_zone", "arguments": arguments},
        },
        headers=headers,
    )
    body = parse_sse_data(response.text)
    result = body.get("result", {})
    success = "error" not in body and not result.get("isError", True)
    return success, body


_CASES: list[tuple[str, dict[str, Any], bool]] = [
    ("happy", {"name": "production-floor"}, True),
    ("empty_name", {"name": ""}, False),
    ("overlong_name", {"name": "x" * 201}, False),
    ("name_missing", {}, False),
]


@pytest.mark.contract
@pytest.mark.parametrize("label,arguments,expected_success", _CASES, ids=[c[0] for c in _CASES])
def test_define_zone_rest_and_mcp_agree_on_outcome(
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

    if rest_success:
        assert "zone_id" in rest_body, f"[{label}] REST success body missing zone_id: {rest_body!r}"
        mcp_zone_id = mcp_body.get("result", {}).get("structuredContent", {}).get("zone_id")
        assert mcp_zone_id is not None, (
            f"[{label}] MCP success body missing structuredContent.zone_id: {mcp_body!r}"
        )
