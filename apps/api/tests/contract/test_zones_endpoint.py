"""Contract tests for `POST /zones`.

Mirror of `test_actors_endpoint.py` for the Trust BC's first slice.
Verifies the HTTP surface: request schema, response schema, status
codes, and that domain errors (e.g. whitespace-only name) translate
to the right HTTP status via the BC exception handlers.
"""

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.trust.aggregates.zone import ZONE_NAME_MAX_LENGTH


@pytest.mark.contract
def test_post_zones_returns_201_with_zone_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/zones", json={"name": "Detector"})

    assert response.status_code == 201
    body = response.json()
    assert "zone_id" in body
    UUID(body["zone_id"])  # parses without raising


@pytest.mark.contract
def test_post_zones_trims_whitespace_in_name() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/zones", json={"name": "  Detector  "})
    assert response.status_code == 201


@pytest.mark.contract
def test_post_zones_rejects_missing_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/zones", json={})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_zones_rejects_empty_name_with_422() -> None:
    """Pydantic min_length=1 catches empty strings before the domain layer."""
    with TestClient(create_app()) as client:
        response = client.post("/zones", json={"name": ""})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_zones_rejects_too_long_name_with_422() -> None:
    """Pydantic max_length=200 catches over-length names."""
    with TestClient(create_app()) as client:
        response = client.post("/zones", json={"name": "a" * 201})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_zones_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only passes Pydantic but the domain VO trims and rejects."""
    with TestClient(create_app()) as client:
        response = client.post("/zones", json={"name": "   "})
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


@pytest.mark.contract
def test_post_zones_uses_max_length_constant_from_domain() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/zones",
            json={"name": "a" * ZONE_NAME_MAX_LENGTH},
        )
    assert response.status_code == 201
