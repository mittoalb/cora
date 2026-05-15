"""Contract tests for `POST /clearances`.

Covers create-style basics (request schema, response shape, status
codes), the StrEnum kind validation at the API boundary (-> 422),
the discriminated-union binding shapes (Subject / Asset / Run /
Procedure / External), the discriminated-union HazardClassification
shapes (NFPA704 / RiskBand / GHS / Scheme), the domain-VO validation
when whitespace-only slips past Pydantic (-> 400), and the
AlreadyExists defensive guard (-> 409 via dependency_overrides).
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.safety.aggregates.clearance import (
    CLEARANCE_TITLE_MAX_LENGTH,
    ClearanceAlreadyExistsError,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features.register_clearance.route import (
    _get_handler as _get_register_clearance_handler,  # pyright: ignore[reportPrivateUsage]
)


def _minimal_body() -> dict[str, object]:
    return {
        "kind": "ESAF",
        "title": "Pilot ESAF for 35-BM",
        "bindings": [{"kind": "Run", "id": str(uuid4())}],
    }


@pytest.mark.contract
def test_post_clearances_returns_201_with_clearance_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=_minimal_body())
    assert response.status_code == 201
    body = response.json()
    assert "clearance_id" in body
    UUID(body["clearance_id"])


@pytest.mark.contract
@pytest.mark.parametrize(
    "kind",
    [
        "ESAF",
        "SAF",
        "AForm",
        "ESRFSAF",
        "DUO",
        "ESRA",
        "ERA",
        "PLHD",
        "DOOR",
        "ESAF_ALS",
        "BTR",
        "Form9",
    ],
)
def test_post_clearances_accepts_each_clearance_kind(kind: str) -> None:
    body = _minimal_body()
    body["kind"] = kind
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=body)
    assert response.status_code == 201, response.json()


@pytest.mark.contract
def test_post_clearances_accepts_multi_binding_request() -> None:
    body = _minimal_body()
    body["bindings"] = [
        {"kind": "Run", "id": str(uuid4())},
        {"kind": "Subject", "id": str(uuid4())},
        {"kind": "Asset", "id": str(uuid4())},
        {"kind": "External", "scheme": "proposal", "id": "GUP-12345"},
    ]
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=body)
    assert response.status_code == 201


@pytest.mark.contract
def test_post_clearances_accepts_optional_risk_band_and_external_id() -> None:
    body = _minimal_body()
    body["risk_band"] = "Yellow"
    body["external_id"] = "ESAF-12345"
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=body)
    assert response.status_code == 201


@pytest.mark.contract
def test_post_clearances_accepts_declarations_with_classifications() -> None:
    sid = str(uuid4())
    body: dict[str, object] = {
        "kind": "ESAF",
        "title": "With hazards",
        "bindings": [{"kind": "Subject", "id": sid}],
        "declarations": [
            {
                "target": {"kind": "Subject", "id": sid},
                "classifications": [
                    {
                        "kind": "NFPA704",
                        "health": 2,
                        "flammability": 1,
                        "instability": 0,
                        "special": "OX",
                    },
                    {"kind": "RiskBand", "band": "Yellow"},
                    {"kind": "GHS", "code": "GHS06", "statement_codes": ["H300"]},
                    {"kind": "Scheme", "scheme": "BSL", "code": "BSL_2", "severity_label": ""},
                ],
                "mitigations": ["ppe:gloves", "training:hazcom-2026"],
                "notes": "Multi-scheme classification",
            }
        ],
    }
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=body)
    assert response.status_code == 201, response.json()


@pytest.mark.contract
def test_post_clearances_rejects_missing_required_fields_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json={"kind": "ESAF"})
    assert response.status_code == 422


@pytest.mark.contract
def test_post_clearances_rejects_unknown_kind_with_422() -> None:
    body = _minimal_body()
    body["kind"] = "Unknown"
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_clearances_rejects_empty_bindings_with_422() -> None:
    body = _minimal_body()
    body["bindings"] = []
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_clearances_rejects_too_long_title_with_422() -> None:
    body = _minimal_body()
    body["title"] = "a" * (CLEARANCE_TITLE_MAX_LENGTH + 1)
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_clearances_rejects_whitespace_only_title_with_400() -> None:
    """Whitespace-only title passes Pydantic min_length=1 but trips the domain VO."""
    body = _minimal_body()
    body["title"] = "   "
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=body)
    assert response.status_code == 400
    assert "Clearance title" in response.json()["detail"]


@pytest.mark.contract
def test_post_clearances_rejects_unknown_binding_kind_with_422() -> None:
    body = _minimal_body()
    body["bindings"] = [{"kind": "Mystery", "id": str(uuid4())}]
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_clearances_rejects_nfpa704_quadrant_above_4_with_422() -> None:
    sid = str(uuid4())
    body: dict[str, object] = {
        "kind": "ESAF",
        "title": "Bad NFPA",
        "bindings": [{"kind": "Subject", "id": sid}],
        "declarations": [
            {
                "target": {"kind": "Subject", "id": sid},
                "classifications": [
                    {"kind": "NFPA704", "health": 5, "flammability": 0, "instability": 0}
                ],
            }
        ],
    }
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=body)
    assert response.status_code == 422


@pytest.mark.contract
async def test_post_clearances_returns_409_when_handler_raises_already_exists() -> None:
    """Defensive guard: stream-already-has-events maps to 409."""
    app = create_app()
    existing_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise ClearanceAlreadyExistsError(existing_id)

    app.dependency_overrides[_get_register_clearance_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/clearances", json=_minimal_body())
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_clearances_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_register_clearance_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/clearances", json=_minimal_body())
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_clearances_accepts_validity_window() -> None:
    body = _minimal_body()
    body["valid_from"] = "2026-05-15T00:00:00+00:00"
    body["valid_until"] = "2026-06-15T00:00:00+00:00"
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=body)
    assert response.status_code == 201


@pytest.mark.contract
def test_post_clearances_rejects_inverted_validity_window_with_400() -> None:
    body = _minimal_body()
    body["valid_from"] = "2026-06-15T00:00:00+00:00"
    body["valid_until"] = "2026-05-15T00:00:00+00:00"
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=body)
    assert response.status_code == 400


@pytest.mark.contract
def test_post_clearances_rejects_zero_duration_validity_window_with_400() -> None:
    """`valid_from == valid_until` is a degenerate zero-duration window;
    rejected at the decider per the same rationale as inverted windows."""
    body = _minimal_body()
    body["valid_from"] = "2026-05-15T00:00:00+00:00"
    body["valid_until"] = "2026-05-15T00:00:00+00:00"
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=body)
    assert response.status_code == 400


@pytest.mark.contract
def test_post_clearances_rejects_malformed_datetime_with_422() -> None:
    """Malformed `valid_from` is parsed by Pydantic, returns 422 not 500."""
    body = _minimal_body()
    body["valid_from"] = "not-a-date"
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_clearances_rejects_declaration_target_not_in_bindings_with_400() -> None:
    """A HazardDeclaration referencing a Subject NOT in the Clearance's
    bindings set is incoherent (the Clearance can't gate against
    out-of-scope targets). Decider rejects with 400."""
    sid_in_set = str(uuid4())
    sid_out_of_set = str(uuid4())
    body: dict[str, object] = {
        "kind": "ESAF",
        "title": "Target out of scope",
        "bindings": [{"kind": "Subject", "id": sid_in_set}],
        "declarations": [
            {
                "target": {"kind": "Subject", "id": sid_out_of_set},
                "classifications": [],
                "mitigations": [],
                "notes": None,
            }
        ],
    }
    with TestClient(create_app()) as client:
        response = client.post("/clearances", json=body)
    assert response.status_code == 400
    assert "not present in the Clearance's bindings" in response.json()["detail"]
