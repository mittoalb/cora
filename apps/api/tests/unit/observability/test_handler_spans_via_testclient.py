"""End-to-end check that handler spans land in the exporter on a real request.

The `spans` fixture installs a fresh global TracerProvider with an in-
memory exporter. `create_app()` with `otel_exporter=none` (the test
default) does NOT call `configure_tracing` and does NOT install
FastAPIInstrumentor, so the only spans we expect are the ones the
`with_tracing` composition wrapper in `cora.access.wire` creates around
each handler call. That's the seam we want to verify here.

Verifying the FastAPIInstrumentor server-kind span on top would require
running with `otel_exporter=console` and replacing the configured
exporter, which is more invasive than this test buys us — that path is
covered by the FastAPIInstrumentor library's own test suite.
"""

import pytest
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from cora.api.main import create_app


@pytest.mark.unit
def test_register_actor_emits_command_span(spans: InMemorySpanExporter) -> None:
    """POST /actors → one `access.command.RegisterActor` span finishes."""
    with TestClient(create_app()) as client:
        response = client.post("/actors", json={"name": "Doga"})

    assert response.status_code == 201
    finished = spans.get_finished_spans()
    register_spans = [s for s in finished if s.name == "access.command.RegisterActor"]
    assert len(register_spans) == 1
    span = register_spans[0]
    assert span.attributes is not None
    assert span.attributes.get("cora.bc") == "access"
    assert span.attributes.get("cora.command") == "RegisterActor"


@pytest.mark.unit
def test_get_actor_emits_query_span(spans: InMemorySpanExporter) -> None:
    """GET /actors/{id} → one `access.query.GetActor` span finishes."""
    with TestClient(create_app()) as client:
        # Create something to read.
        created = client.post("/actors", json={"name": "Doga"}).json()
        actor_id = created["actor_id"]
        spans.clear()  # only assert on the GET-triggered spans

        response = client.get(f"/actors/{actor_id}")

    assert response.status_code == 200
    finished = spans.get_finished_spans()
    query_spans = [s for s in finished if s.name == "access.query.GetActor"]
    assert len(query_spans) == 1
    span = query_spans[0]
    assert span.attributes is not None
    assert span.attributes.get("cora.bc") == "access"
    assert span.attributes.get("cora.query") == "GetActor"
