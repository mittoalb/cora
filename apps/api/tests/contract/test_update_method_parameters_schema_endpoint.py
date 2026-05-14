"""Contract tests for `POST /methods/{method_id}/parameters-schema`.

Phase 6g-a. Action endpoint with body `{parameters_schema}`. Schema
can be set, replaced, or cleared (null payload). Mirrors
`test_update_capability_schema_endpoint.py` (5g-a).
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _define_method(client: TestClient, name: str = "XRF Mapping") -> UUID:
    response = client.post(
        "/methods",
        json={"name": name, "needs_capabilities": []},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["method_id"])


def _example_schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy_kev": {"type": "number", "minimum": 5, "maximum": 50},
        },
        "required": ["energy_kev"],
    }


@pytest.mark.contract
def test_post_update_method_parameters_schema_returns_204_when_setting_schema() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={"parameters_schema": _example_schema()},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_update_method_parameters_schema_returns_204_when_clearing_schema() -> None:
    """Pass null to clear a previously-set schema."""
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        first = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={"parameters_schema": _example_schema()},
        )
        assert first.status_code == 204
        cleared = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={"parameters_schema": None},
        )
    assert cleared.status_code == 204


@pytest.mark.contract
def test_post_update_method_parameters_schema_returns_400_for_missing_dollar_schema() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={"parameters_schema": {"type": "object"}},  # missing $schema
        )
    assert response.status_code == 400
    body = response.json()
    assert "Invalid Method parameters_schema" in body["detail"]


@pytest.mark.contract
def test_post_update_method_parameters_schema_returns_400_for_forbidden_keyword() -> None:
    with TestClient(create_app()) as client:
        method_id = _define_method(client)
        response = client.post(
            f"/methods/{method_id}/parameters-schema",
            json={
                "parameters_schema": {
                    "$schema": _DRAFT,
                    "oneOf": [{"type": "string"}, {"type": "integer"}],
                },
            },
        )
    assert response.status_code == 400
    body = response.json()
    assert "forbidden keyword" in body["detail"]


@pytest.mark.contract
def test_post_update_method_parameters_schema_returns_404_for_unknown_method() -> None:
    unknown_id = uuid4()
    with TestClient(create_app()) as client:
        response = client.post(
            f"/methods/{unknown_id}/parameters-schema",
            json={"parameters_schema": _example_schema()},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_update_method_parameters_schema_returns_422_for_malformed_path() -> None:
    """Bad UUID in path -> Pydantic 422."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/methods/not-a-uuid/parameters-schema",
            json={"parameters_schema": None},
        )
    assert response.status_code == 422
