"""Contract tests for `POST /decisions` and `GET /decisions/{id}`."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app


def _good_body(actor_id: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "decided_by": actor_id,
        "context": "RecipeApproval",
        "choice": "Approved",
    }
    base.update(overrides)
    return base


def _register_actor(client: TestClient) -> str:
    return client.post("/actors", json={"name": "Test Operator"}).json()["actor_id"]


# ---------- Happy path ----------


@pytest.mark.contract
def test_post_decisions_returns_201_for_minimal_body() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        response = client.post("/decisions", json=_good_body(actor_id))
    assert response.status_code == 201
    assert "decision_id" in response.json()


@pytest.mark.contract
def test_post_decisions_round_trips_into_get_response() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        create = client.post(
            "/decisions",
            json=_good_body(
                actor_id,
                choice="Conditionally approved with re-test required",
                rule="iso17025:7.1.3:simple_acceptance",
                reasoning="Measurement at 1.234 within tolerance.",
                confidence=0.92,
                confidence_source="human",
                alternatives=["Approve", "Reject", "Re-measure"],
                inputs={"measured_value": 1.234, "limit": 1.5},
            ),
        )
        assert create.status_code == 201
        decision_id = create.json()["decision_id"]
        get = client.get(f"/decisions/{decision_id}")
    assert get.status_code == 200
    body = get.json()
    assert body["id"] == decision_id
    assert body["decided_by"] == actor_id
    assert body["context"] == "RecipeApproval"
    assert body["choice"] == "Conditionally approved with re-test required"
    assert body["rule"] == "iso17025:7.1.3:simple_acceptance"
    assert body["confidence"] == 0.92
    assert body["confidence_source"] == "human"
    assert body["alternatives"] == ["Approve", "Reject", "Re-measure"]
    assert body["inputs"] == {"measured_value": 1.234, "limit": 1.5}


@pytest.mark.contract
def test_post_decisions_chain_with_parent_and_override_kind() -> None:
    """Hybrid AI→human flow: AI decides, human overrides via parent chain."""
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        first = client.post(
            "/decisions",
            json=_good_body(
                actor_id,
                choice="Auto-rejected (low confidence)",
                confidence=0.3,
                confidence_source="logprob",
            ),
        )
        assert first.status_code == 201
        parent_id = first.json()["decision_id"]
        second = client.post(
            "/decisions",
            json=_good_body(
                actor_id,
                choice="Approved (operator override)",
                parent_id=parent_id,
                override_kind="exception",
            ),
        )
    assert second.status_code == 201


# ---------- Cross-aggregate not-found (409) ----------


@pytest.mark.contract
def test_post_decisions_returns_404_when_actor_does_not_exist() -> None:
    """Per the locked `<X>NotFoundError -> 404` taxonomy,
    `DeciderActorNotFoundError` maps to 404: the actor referenced in
    the request body does not exist. The renamed
    `_handle_logbook_state` (was `_handle_cross_agg_conflict`) covers
    only true cross-aggregate state conflicts now; not-found routes
    through `_handle_not_found`."""
    missing = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post("/decisions", json=_good_body(missing))
    assert response.status_code == 404
    assert "decided_by" in response.json()["detail"]


@pytest.mark.contract
def test_post_decisions_returns_404_when_parent_id_does_not_exist() -> None:
    """Same locked taxonomy: `DecisionParentNotFoundError` -> 404."""
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        response = client.post(
            "/decisions",
            json=_good_body(
                actor_id,
                parent_id=str(uuid4()),
                override_kind="correction",
            ),
        )
    assert response.status_code == 404
    assert "parent_id" in response.json()["detail"]


# ---------- override_kind / parent_id consistency (400) ----------


@pytest.mark.contract
def test_post_decisions_returns_400_when_override_kind_without_parent() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        response = client.post(
            "/decisions",
            json=_good_body(actor_id, override_kind="correction"),
        )
    assert response.status_code == 400
    assert "parent_id" in response.json()["detail"].lower()


# ---------- Schema / domain validation ----------


@pytest.mark.contract
def test_post_decisions_rejects_empty_choice_with_422() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        response = client.post("/decisions", json=_good_body(actor_id, choice=""))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_decisions_rejects_whitespace_only_choice_with_400() -> None:
    """Whitespace passes Pydantic min_length but the decider trims and rejects."""
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        response = client.post("/decisions", json=_good_body(actor_id, choice="   "))
    assert response.status_code == 400


@pytest.mark.contract
def test_post_decisions_rejects_confidence_out_of_range_with_422() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        response = client.post("/decisions", json=_good_body(actor_id, confidence=1.5))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_decisions_rejects_extra_fields_with_422() -> None:
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        response = client.post(
            "/decisions",
            json={**_good_body(actor_id), "extra_field": "boom"},
        )
    assert response.status_code == 422


# ---------- GET ----------


@pytest.mark.contract
def test_get_decisions_response_includes_confidence_band_when_confidence_set() -> None:
    """8b derived field: confidence_band surfaces in the GET response."""
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        decision_id = client.post(
            "/decisions",
            json=_good_body(actor_id, confidence=0.85, confidence_source="ensemble"),
        ).json()["decision_id"]
        response = client.get(f"/decisions/{decision_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["confidence"] == 0.85
    assert body["confidence_band"] == "High"


@pytest.mark.contract
def test_get_decisions_response_confidence_band_is_null_when_confidence_null() -> None:
    """Preserves the not-set distinction; never silently maps None to Low."""
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        decision_id = client.post("/decisions", json=_good_body(actor_id)).json()["decision_id"]
        response = client.get(f"/decisions/{decision_id}")
    body = response.json()
    assert body["confidence"] is None
    assert body["confidence_band"] is None


@pytest.mark.contract
@pytest.mark.parametrize(
    ("confidence", "expected_band"),
    [
        (0.1, "Low"),
        (0.5, "Medium"),
        (0.85, "High"),
        (0.99, "Certain"),
    ],
)
def test_get_decisions_response_confidence_band_classification(
    confidence: float, expected_band: str
) -> None:
    """Round-trip the band derivation through HTTP."""
    with TestClient(create_app()) as client:
        actor_id = _register_actor(client)
        decision_id = client.post(
            "/decisions",
            json=_good_body(actor_id, confidence=confidence, confidence_source="logprob"),
        ).json()["decision_id"]
        response = client.get(f"/decisions/{decision_id}")
    assert response.json()["confidence_band"] == expected_band


@pytest.mark.contract
def test_get_decisions_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/decisions/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.contract
def test_get_decisions_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/decisions/not-a-uuid")
    assert response.status_code == 422
