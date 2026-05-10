"""Contract tests for `POST /conduits`.

Mirror of `test_zones_endpoint.py`. Verifies the HTTP surface,
including UUID parsing of the two endpoint zone fields and the
domain-error mapping for whitespace-only conduit names.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.trust.aggregates.conduit import CONDUIT_NAME_MAX_LENGTH

_SOURCE = "01900000-0000-7000-8000-00000000aaaa"
_TARGET = "01900000-0000-7000-8000-00000000bbbb"


def _body(name: str = "Detector-to-Storage", **overrides: str) -> dict[str, str]:
    base = {
        "name": name,
        "source_zone_id": _SOURCE,
        "target_zone_id": _TARGET,
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_post_conduits_returns_201_with_conduit_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/conduits", json=_body())

    assert response.status_code == 201
    body = response.json()
    assert "conduit_id" in body
    UUID(body["conduit_id"])  # parses without raising


@pytest.mark.contract
def test_post_conduits_trims_whitespace_in_name() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/conduits", json=_body(name="  Detector-to-Storage  "))
    assert response.status_code == 201


@pytest.mark.contract
def test_post_conduits_rejects_missing_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/conduits",
            json={"source_zone_id": _SOURCE, "target_zone_id": _TARGET},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_conduits_rejects_missing_source_zone_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/conduits",
            json={"name": "Detector-to-Storage", "target_zone_id": _TARGET},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_conduits_rejects_invalid_uuid_in_source_zone_with_422() -> None:
    """Pydantic UUID parsing rejects non-UUID strings before the handler runs."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/conduits",
            json=_body(source_zone_id="not-a-uuid"),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_conduits_rejects_empty_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/conduits", json=_body(name=""))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_conduits_rejects_too_long_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/conduits", json=_body(name="a" * 201))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_conduits_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only passes Pydantic but the domain VO trims and rejects."""
    with TestClient(create_app()) as client:
        response = client.post("/conduits", json=_body(name="   "))
    assert response.status_code == 400
    body = response.json()
    assert "detail" in body


@pytest.mark.contract
def test_post_conduits_uses_max_length_constant_from_domain() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/conduits",
            json=_body(name="a" * CONDUIT_NAME_MAX_LENGTH),
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_conduits_accepts_dangling_zone_references() -> None:
    """Eventual-consistency stance: source/target Zone existence is NOT
    verified at command time (see Conduit aggregate docstring). Posting
    with random UUIDs that have no corresponding Zone events succeeds.
    Pinned in a contract test so a future "validate at command time"
    refactor would have to flip this."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/conduits",
            json=_body(
                source_zone_id=str(uuid4()),
                target_zone_id=str(uuid4()),
            ),
        )
    assert response.status_code == 201
