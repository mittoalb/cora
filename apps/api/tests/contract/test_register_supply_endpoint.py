"""Contract tests for `POST /supplies`.

Covers create-style basics (request schema, response shape, status
codes), the StrEnum scope-validation at the API boundary (unknown
scopes -> 422), the Pydantic min/max length on kind + name (-> 422),
the FacilityCode regex on `facility_code` (-> 422), the cross-BC
SupplyFacilityNotFound mapping when the slug does not resolve
(-> 404), the domain-VO validation when whitespace-only slips past
Pydantic (-> 400), and the AlreadyExists defensive guard (-> 409 via
dependency_overrides).

The TestClient app bootstraps with `SELF_FACILITY_CODE` defaulting
to `"cora"`, so happy-path requests bind to the self-Facility row
seeded at lifespan. The not-found contract uses an unseeded slug.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.supply.aggregates.supply import (
    SUPPLY_KIND_MAX_LENGTH,
    SUPPLY_NAME_MAX_LENGTH,
    SupplyAlreadyExistsError,
)
from cora.supply.errors import UnauthorizedError
from cora.supply.features.register_supply.route import (
    _get_handler as _get_register_supply_handler,  # pyright: ignore[reportPrivateUsage]
)


@pytest.mark.contract
def test_post_supplies_returns_201_with_supply_id_for_beamline_scope() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/supplies",
            json={
                "scope": "Beamline",
                "kind": "LiquidNitrogen",
                "name": "2-BM LN2",
                "facility_code": "cora",
            },
        )
    assert response.status_code == 201
    body = response.json()
    assert "supply_id" in body
    UUID(body["supply_id"])


@pytest.mark.contract
@pytest.mark.parametrize("scope", ["Facility", "Sector", "Beamline"])
def test_post_supplies_accepts_each_scope(scope: str) -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/supplies",
            json={
                "scope": scope,
                "kind": "LiquidNitrogen",
                "name": f"{scope}-LN2",
                "facility_code": "cora",
            },
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_supplies_trims_whitespace_in_kind_and_name() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/supplies",
            json={
                "scope": "Beamline",
                "kind": "LiquidNitrogen",
                "name": "  2-BM LN2  ",
                "facility_code": "cora",
            },
        )
    assert response.status_code == 201


@pytest.mark.contract
def test_post_supplies_rejects_missing_required_fields_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/supplies", json={"scope": "Beamline"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_supplies_rejects_missing_facility_code_with_422() -> None:
    """Slice 7A: facility_code is required at the API boundary."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/supplies",
            json={"scope": "Beamline", "kind": "X", "name": "Y"},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_supplies_rejects_unknown_scope_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/supplies",
            json={
                "scope": "Galaxy",
                "kind": "X",
                "name": "Y",
                "facility_code": "cora",
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_supplies_rejects_empty_kind_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/supplies",
            json={
                "scope": "Beamline",
                "kind": "",
                "name": "X",
                "facility_code": "cora",
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_supplies_rejects_too_long_kind_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/supplies",
            json={
                "scope": "Beamline",
                "kind": "a" * (SUPPLY_KIND_MAX_LENGTH + 1),
                "name": "X",
                "facility_code": "cora",
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_supplies_rejects_too_long_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/supplies",
            json={
                "scope": "Beamline",
                "kind": "X",
                "name": "a" * (SUPPLY_NAME_MAX_LENGTH + 1),
                "facility_code": "cora",
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
@pytest.mark.parametrize(
    "bad_code",
    ["APS", "_underscore", "with space", "a" * 33, ""],
)
def test_post_supplies_rejects_malformed_facility_code_with_422(bad_code: str) -> None:
    """FacilityCode regex (lowercase ASCII alphanumeric + dash, 1-32 chars)
    enforced at the Pydantic boundary. Uppercase, underscores, spaces,
    over-length, and empty all reject before reaching the handler."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/supplies",
            json={
                "scope": "Beamline",
                "kind": "LiquidNitrogen",
                "name": "X",
                "facility_code": bad_code,
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_supplies_returns_404_when_facility_code_unseeded() -> None:
    """Slice 7A cross-BC binding: an unknown but well-formed slug
    surfaces as SupplyFacilityNotFoundError -> 404."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/supplies",
            json={
                "scope": "Beamline",
                "kind": "LiquidNitrogen",
                "name": "2-BM LN2",
                "facility_code": "unseeded",
            },
        )
    assert response.status_code == 404
    assert "unseeded" in response.json()["detail"]


@pytest.mark.contract
def test_post_supplies_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace-only name passes Pydantic min_length=1 but trips the domain VO."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/supplies",
            json={
                "scope": "Beamline",
                "kind": "LiquidNitrogen",
                "name": "   ",
                "facility_code": "cora",
            },
        )
    assert response.status_code == 400
    assert "Supply name" in response.json()["detail"]


@pytest.mark.contract
def test_post_supplies_rejects_whitespace_only_kind_with_400() -> None:
    """Whitespace-only kind passes Pydantic min_length=1 but trips the decider validator."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/supplies",
            json={
                "scope": "Beamline",
                "kind": "   ",
                "name": "X",
                "facility_code": "cora",
            },
        )
    assert response.status_code == 400
    assert "Supply kind" in response.json()["detail"]


@pytest.mark.contract
async def test_post_supplies_returns_409_when_handler_raises_already_exists() -> None:
    """Defensive guard: stream-already-has-events maps to 409."""
    app = create_app()
    existing_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise SupplyAlreadyExistsError(existing_id)

    app.dependency_overrides[_get_register_supply_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/supplies",
            json={
                "scope": "Beamline",
                "kind": "X",
                "name": "Y",
                "facility_code": "cora",
            },
        )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_supplies_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_register_supply_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/supplies",
            json={
                "scope": "Beamline",
                "kind": "LiquidNitrogen",
                "name": "2-BM LN2",
                "facility_code": "cora",
            },
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
