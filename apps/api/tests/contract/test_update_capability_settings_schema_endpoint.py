"""Contract tests for `POST /capabilities/{capability_id}/settings-schema`.

Phase 5g-a. Action endpoint with body `{settings_schema}`. Schema
can be set, replaced, or cleared (null payload).
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _define_capability(client: TestClient, name: str = "Tomography") -> UUID:
    response = client.post("/capabilities", json={"name": name})
    assert response.status_code == 201
    return UUID(response.json()["capability_id"])


def _example_schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": 5,
                "maximum": 50,
                "unit": {"system": "udunits", "code": "keV"},
            },
        },
        "required": ["energy"],
    }


@pytest.mark.contract
def test_post_update_capability_settings_schema_returns_204_when_setting_schema() -> None:
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client)
        response = client.post(
            f"/capabilities/{capability_id}/settings-schema",
            json={"settings_schema": _example_schema()},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_update_capability_settings_schema_returns_204_when_clearing_schema() -> None:
    """Pass null to clear a previously-set schema."""
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client)
        first = client.post(
            f"/capabilities/{capability_id}/settings-schema",
            json={"settings_schema": _example_schema()},
        )
        assert first.status_code == 204
        cleared = client.post(
            f"/capabilities/{capability_id}/settings-schema",
            json={"settings_schema": None},
        )
    assert cleared.status_code == 204


@pytest.mark.contract
def test_post_update_capability_settings_schema_returns_400_for_missing_dollar_schema() -> None:
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client)
        response = client.post(
            f"/capabilities/{capability_id}/settings-schema",
            json={"settings_schema": {"type": "object"}},  # missing $schema
        )
    assert response.status_code == 400
    body = response.json()
    assert "Invalid Capability settings_schema" in body["detail"]


@pytest.mark.contract
def test_post_update_capability_settings_schema_returns_400_for_forbidden_keyword() -> None:
    with TestClient(create_app()) as client:
        capability_id = _define_capability(client)
        response = client.post(
            f"/capabilities/{capability_id}/settings-schema",
            json={
                "settings_schema": {
                    "$schema": _DRAFT,
                    "oneOf": [{"type": "string"}, {"type": "integer"}],
                },
            },
        )
    assert response.status_code == 400
    body = response.json()
    assert "forbidden keyword" in body["detail"]


@pytest.mark.contract
def test_post_update_capability_settings_schema_returns_404_for_unknown_capability() -> None:
    unknown_id = uuid4()
    with TestClient(create_app()) as client:
        response = client.post(
            f"/capabilities/{unknown_id}/settings-schema",
            json={"settings_schema": _example_schema()},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_update_capability_settings_schema_returns_422_for_malformed_path() -> None:
    """Bad UUID in path -> Pydantic 422."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/capabilities/not-a-uuid/settings-schema",
            json={"settings_schema": None},
        )
    assert response.status_code == 422
