"""Contract tests for the Prometheus `/metrics` endpoint.

Covers that the endpoint exists, returns Prometheus text-exposition
format, and that the standard request-count metric appears after a
real route is exercised.
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


@pytest.mark.contract
def test_metrics_endpoint_exists_and_returns_prometheus_format() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    # Prometheus text format starts with HELP/TYPE comment lines.
    assert "# HELP" in body
    assert "# TYPE" in body


@pytest.mark.contract
def test_metrics_records_request_count_after_real_request() -> None:
    """After hitting /health, the http_requests_total counter increments."""
    with TestClient(create_app()) as client:
        client.get("/health")
        response = client.get("/metrics")

    body = response.text
    assert "http_requests_total" in body
    # The /health request shows up as a labelled series.
    assert 'handler="/health"' in body
