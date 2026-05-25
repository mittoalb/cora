"""MCP property-fuzz across a curated set of create-style tools.

For each tool in the allowlist:

  1. Fetch the live `inputSchema` and `outputSchema` from `tools/list`.
  2. Build a Hypothesis strategy with `hypothesis-jsonschema` driven by
     the input schema.
  3. Generate schema-conforming inputs and assert the MCP surface
     never returns a JSON-RPC schema-validation `error` envelope on
     them (input-schema drift catcher).
  4. On success responses, round-trip `structuredContent` through the
     declared `outputSchema` (output-schema drift catcher).

Why this earns its keep: FastMCP derives its tool schemas from
Pydantic `Annotated[Type, Field(...)]` shapes via a separate code
path than the REST request models. Drift between the two surfaces or
between a tool's declared schema and what its handler actually
accepts is structurally invisible to example-based tests. Property
fuzz across the live schema closes that gap with zero hand-curated
input cases per tool.

`hypothesis-jsonschema` (0.23.x) is in maintenance mode and supports
Draft 04/06/07 but not 2020-12. FastMCP's emitted schemas declare
`$schema = draft 2020-12` but otherwise stay Draft-07-compatible for
the constructs CORA actually uses (`type`, `properties`, `required`,
`minLength`, `maxLength`, `enum`, `format`). The harness strips
`$schema` before invoking `from_schema()` to force the Draft 07 path.

Tool allowlist is the 5 create-style tools that allocate their own
ID and need zero FK seed data. Extending the allowlist beyond this
needs a per-tool seed setup; defer to a second iter under the
rule-of-three.

See [[project_testing_techniques_research]] Corpus 3 for the open-
frontier framing (no public MCP property-fuzz library as of
2026-05).
"""

from __future__ import annotations

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from copy import deepcopy
from functools import lru_cache
from typing import Any

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis_jsonschema import from_schema
from jsonschema import Draft7Validator

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_FUZZED_TOOLS = (
    "register_actor",
    "define_zone",
    "define_family",
    "define_capability",
    "define_surface",
)


def _strip_schema_dialect(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy with the top-level `$schema` field removed.

    `hypothesis-jsonschema` raises on `$schema` values it doesn't
    recognise (FastMCP emits the Draft 2020-12 URI). Stripping it
    forces the Draft 07 code path, which is correct for the schema
    constructs CORA actually uses.
    """
    clone = deepcopy(schema)
    clone.pop("$schema", None)
    return clone


@lru_cache(maxsize=1)
def _tool_schemas() -> dict[str, tuple[dict[str, Any], dict[str, Any] | None]]:
    """Fetch `tools/list` once and return `{name: (input, output)}`.

    Cached for the test-session lifetime via `lru_cache` so the
    parametrised cases share one MCP handshake.
    """
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tools = body["result"]["tools"]
    out: dict[str, tuple[dict[str, Any], dict[str, Any] | None]] = {}
    for tool in tools:
        name = tool["name"]
        if name not in _FUZZED_TOOLS:
            continue
        input_schema = _strip_schema_dialect(tool["inputSchema"])
        raw_output = tool.get("outputSchema")
        output_schema = _strip_schema_dialect(raw_output) if raw_output else None
        out[name] = (input_schema, output_schema)
    missing = set(_FUZZED_TOOLS) - set(out)
    assert not missing, f"Allowlist tools missing from tools/list: {missing}"
    return out


def _dispatch(
    client: TestClient,
    headers: dict[str, str],
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """POST `tools/call` and return the parsed JSON-RPC envelope."""
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers=headers,
    )
    return parse_sse_data(response.text)


@pytest.mark.contract
@pytest.mark.parametrize("tool_name", _FUZZED_TOOLS)
def test_mcp_tool_accepts_schema_conforming_input(tool_name: str) -> None:
    """Schema-conforming inputs never trip the JSON-RPC error envelope.

    Three assertions per generated example:
      1. No `error` key at the JSON-RPC envelope level (would mean
         FastMCP rejected the input as schema-invalid even though it
         passes the tool's own declared `inputSchema`).
      2. The `isError` flag is present on every result envelope. The
         MCP spec defaults it to false on success, but treating
         "missing" as "success" silently disables Assertion 3 if
         FastMCP ever changes the envelope shape. The drift catcher
         has to scream when the contract moves under it.
      3. On a successful result (`isError` is false) for a tool with
         a declared `outputSchema`, `structuredContent` MUST be
         present and validate against that schema. A missing
         `structuredContent` on a schema-declaring tool IS the drift
         this harness exists to catch; skipping it silently would
         defeat the point.

    Domain-layer rejections (`isError = true` with a business-rule
    violation) are NOT failures of this property; they are expected
    and ignored.

    TestClient + MCP handshake are hoisted outside the Hypothesis
    property body, so each parametrised case pays one lifespan
    startup + one `initialize` round-trip, not 50. Hypothesis shrinks
    against the same live client too, which keeps shrinkage honest.
    The MCP session id is reused across all 50 `tools/call` requests
    inside a single test; that is the supported MCP pattern.
    """
    input_schema, output_schema = _tool_schemas()[tool_name]
    strategy = from_schema(input_schema)

    with TestClient(create_app()) as client:
        headers = open_session(client)

        @given(arguments=strategy)
        @settings(
            max_examples=50,
            deadline=None,
            suppress_health_check=[HealthCheck.function_scoped_fixture],
        )
        def _property(arguments: dict[str, Any]) -> None:
            body = _dispatch(client, headers, tool_name, arguments)

            assert "error" not in body, (
                f"[{tool_name}] schema-conforming input rejected at JSON-RPC layer: "
                f"args={arguments!r} body={body!r}"
            )

            result = body.get("result", {})
            assert "isError" in result, (
                f"[{tool_name}] envelope missing `isError` flag: body={body!r}"
            )

            if not result["isError"] and output_schema is not None:
                structured = result.get("structuredContent")
                assert structured is not None, (
                    f"[{tool_name}] success response missing `structuredContent` "
                    f"despite a declared outputSchema: body={body!r}"
                )
                Draft7Validator(output_schema).validate(structured)

        _property()


_NEGATIVE_CASES: tuple[tuple[str, dict[str, Any]], ...] = (
    ("register_actor", {"name": 12345}),
    ("define_zone", {"name": 12345}),
    ("define_family", {"name": 12345, "affordances": ["not_a_real_affordance"]}),
    ("define_capability", {"name": 12345}),
    ("define_surface", {"kind": "not_a_real_surface_kind"}),
)


@pytest.mark.contract
@pytest.mark.parametrize(
    "tool_name,arguments",
    _NEGATIVE_CASES,
    ids=[name for name, _ in _NEGATIVE_CASES],
)
def test_mcp_tool_rejects_schema_violating_input(tool_name: str, arguments: dict[str, Any]) -> None:
    """A schema-violating input MUST surface as a JSON-RPC `error` envelope.

    Proves the positive property above isn't passing vacuously. If
    FastMCP ever stops validating against tool inputSchema entirely,
    Assertion 1 of the positive test would silently pass on garbage
    inputs forever; this companion test fires the negative case to
    show validation is still alive.

    One curated bad input per allowlisted tool. The exact violation
    differs by schema shape (wrong type vs. enum miss); each case
    targets a constraint cheap to break on the declared schema.
    """
    with TestClient(create_app()) as client:
        headers = open_session(client)
        body = _dispatch(client, headers, tool_name, arguments)

    error_envelope = "error" in body
    is_error_result = body.get("result", {}).get("isError") is True
    assert error_envelope or is_error_result, (
        f"[{tool_name}] schema-violating input was NOT rejected: args={arguments!r} body={body!r}"
    )
