"""Contract tests for the `dismiss_event_in_reaction` MCP tool.

The slice is PG-bound; in the in-memory test app the handler raises
DismissalRequiresPostgresError. The MCP tool surfaces this as
isError=True. Production deploys with a Postgres pool exercise the
happy path in the integration suite.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data


@pytest.mark.contract
def test_mcp_lists_dismiss_event_in_reaction_tool() -> None:
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 99, "method": "tools/list"},
            headers=headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "dismiss_event_in_reaction" in tool_names


@pytest.mark.contract
def test_mcp_dismiss_event_in_reaction_tool_iserror_in_memory_mode() -> None:
    """In-memory app surfaces DismissalRequiresPostgresError as
    isError=True on the MCP tool. Production deploys never see this
    branch."""
    with TestClient(create_app()) as client:
        headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "dismiss_event_in_reaction",
                    "arguments": {
                        "subscriber_name": "run_debriefer",
                        "event_id": str(uuid4()),
                        "reason": "test",
                    },
                },
            },
            headers=headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
    assert "postgres" in body["result"]["content"][0]["text"].lower()
