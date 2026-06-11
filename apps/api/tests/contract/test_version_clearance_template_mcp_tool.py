"""Contract tests for the `version_clearance_template` MCP tool.

Pins tool registration on the MCP server, the input-schema requirements
(`template_id`, `new_version`, `supersedes_template_id` all required;
`new_version` carries `minimum=2` since the first published version is
`Active` v1 and a versioning event records v2 onward), the structured
output shape (`VersionClearanceTemplateOutput` carrying `template_id`
round-tripped), handler-side exception bubbling as `isError: true` (the
FastMCP idiom REST surfaces as 4xx for the same condition), and the
Authorize-Deny path bubbling as `isError: true` (mirrors how the
production `TrustAuthorize` would on a Deny).
"""

from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.safety.errors import UnauthorizedError
from tests.contract._mcp_helpers import open_session, parse_sse_data

_FACILITY_CODE = "cora"


def _version_template_via_tool(
    client: TestClient,
    session_headers: dict[str, str],
    *,
    template_id: UUID,
    new_version: int = 2,
    supersedes_template_id: UUID | None = None,
    rpc_id: int = 101,
) -> dict[str, Any]:
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": "tools/call",
            "params": {
                "name": "version_clearance_template",
                "arguments": {
                    "template_id": str(template_id),
                    "new_version": new_version,
                    "supersedes_template_id": str(
                        supersedes_template_id if supersedes_template_id is not None else uuid4()
                    ),
                },
            },
        },
        headers=session_headers,
    )
    assert response.status_code == 200, response.text
    return parse_sse_data(response.text)


@pytest.mark.contract
def test_mcp_lists_version_clearance_template_tool() -> None:
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
    assert "version_clearance_template" in tool_names


@pytest.mark.contract
def test_mcp_version_clearance_template_input_schema_pins_required_args() -> None:
    """All three args -- template_id, new_version, supersedes_template_id --
    must be advertised as required."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tools = {t["name"]: t for t in body["result"]["tools"]}
    schema = tools["version_clearance_template"]["inputSchema"]
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    assert {"template_id", "new_version", "supersedes_template_id"}.issubset(properties.keys())
    assert {"template_id", "new_version", "supersedes_template_id"}.issubset(required)


@pytest.mark.contract
def test_mcp_version_clearance_template_input_schema_pins_new_version_minimum_two() -> None:
    """`new_version` carries `minimum=2`; v1 lands at activation and the
    versioning slice records v2 and onward."""
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tools = {t["name"]: t for t in body["result"]["tools"]}
    schema = tools["version_clearance_template"]["inputSchema"]
    new_version_schema = schema["properties"]["new_version"]
    assert new_version_schema.get("minimum") == 2


@pytest.mark.contract
def test_mcp_version_clearance_template_tool_returns_structured_template_id() -> None:
    """Happy path: replace the wired handler with a no-op; the tool
    returns `VersionClearanceTemplateOutput` carrying `template_id`."""
    template_id = uuid4()
    supersedes_template_id = uuid4()

    async def _noop_handler(*_args: object, **_kwargs: object) -> None:
        return None

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            version_clearance_template=_noop_handler,
        )
        session_headers = open_session(client)
        body = _version_template_via_tool(
            client,
            session_headers,
            template_id=template_id,
            new_version=2,
            supersedes_template_id=supersedes_template_id,
        )

    result = body["result"]
    assert result["isError"] is False, result
    structured = result["structuredContent"]
    assert structured["template_id"] == str(template_id)
    UUID(structured["template_id"])


@pytest.mark.contract
def test_mcp_version_clearance_template_tool_returns_iserror_on_handler_exception() -> None:
    """Decider/handler-layer exceptions (e.g. unknown template, non-Active
    state, monotonic violation, facility mismatch) bubble through FastMCP
    as `isError: true` -- the same idiom REST surfaces as 4xx."""

    async def _raising_handler(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("template not Active")

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            version_clearance_template=_raising_handler,
        )
        session_headers = open_session(client)
        body = _version_template_via_tool(
            client,
            session_headers,
            template_id=uuid4(),
            new_version=2,
            supersedes_template_id=uuid4(),
            rpc_id=300,
        )

    assert body["result"]["isError"] is True


@pytest.mark.contract
def test_mcp_version_clearance_template_tool_authorize_deny_bubbles_as_iserror() -> None:
    """Replace the wired handler with one that raises `UnauthorizedError`,
    mirroring how the production `TrustAuthorize` would on a Deny. The MCP
    tool surfaces it as `isError: true` per the FastMCP contract."""

    async def _denying_handler(*_args: object, **_kwargs: object) -> None:
        raise UnauthorizedError("denied for test")

    with TestClient(create_app()) as client:
        client.app.state.safety = replace(  # type: ignore[attr-defined]
            client.app.state.safety,  # type: ignore[attr-defined]
            version_clearance_template=_denying_handler,
        )
        session_headers = open_session(client)
        body = _version_template_via_tool(
            client,
            session_headers,
            template_id=uuid4(),
            new_version=2,
            supersedes_template_id=uuid4(),
            rpc_id=400,
        )

    assert body["result"]["isError"] is True
