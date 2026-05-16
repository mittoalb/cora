"""Contract tests for the `remove_run_from_campaign` MCP tool."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.infrastructure.event_envelope import to_new_event
from cora.run.aggregates.run import (
    event_type_name as run_event_type_name,
)
from cora.run.aggregates.run import (
    to_payload as run_to_payload,
)
from cora.run.aggregates.run.events import RunStarted
from tests.contract._mcp_helpers import open_session, parse_sse_data

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)


def _seed_active_campaign(client: TestClient) -> str:
    response = client.post(
        "/campaigns",
        json={"name": "test", "intent": "InSitu", "lead_actor_id": str(uuid4())},
    )
    cid = str(response.json()["campaign_id"])
    client.post(f"/campaigns/{cid}/start")
    return cid


def _seed_run(app: FastAPI, run_id: UUID) -> None:
    event = RunStarted(
        run_id=run_id,
        name="contract-test-run",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=run_event_type_name(event),
        payload=run_to_payload(event),
        occurred_at=event.occurred_at,
        event_id=uuid4(),
        command_name="seed",
        correlation_id=uuid4(),
        causation_id=None,
        principal_id=uuid4(),
    )
    asyncio.run(
        app.state.deps.event_store.append("Run", run_id, 0, [new_event]),
    )


def _add_member(client: TestClient, app: FastAPI, cid: str) -> UUID:
    run_id = uuid4()
    _seed_run(app, run_id)
    client.post(f"/campaigns/{cid}/runs/{run_id}")
    return run_id


@pytest.mark.contract
def test_mcp_lists_remove_run_from_campaign_tool() -> None:
    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    tool_names = [t["name"] for t in body["result"]["tools"]]
    assert "remove_run_from_campaign" in tool_names


@pytest.mark.contract
def test_mcp_remove_run_from_campaign_tool_returns_structured_ids() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid = _seed_active_campaign(client)
        run_id = _add_member(client, app, cid)
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "remove_run_from_campaign",
                    "arguments": {
                        "campaign_id": cid,
                        "run_id": str(run_id),
                        "reason": "removed by operator",
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    result = body["result"]
    assert result["isError"] is False, result
    assert result["structuredContent"]["campaign_id"] == cid
    assert result["structuredContent"]["run_id"] == str(run_id)


@pytest.mark.contract
def test_mcp_remove_run_from_campaign_tool_returns_iserror_when_not_member() -> None:
    app = create_app()
    with TestClient(app) as client:
        cid = _seed_active_campaign(client)
        run_id = uuid4()
        _seed_run(app, run_id)  # not added
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "remove_run_from_campaign",
                    "arguments": {
                        "campaign_id": cid,
                        "run_id": str(run_id),
                        "reason": "x",
                    },
                },
            },
            headers=session_headers,
        )
    body = parse_sse_data(response.text)
    assert body["result"]["isError"] is True
