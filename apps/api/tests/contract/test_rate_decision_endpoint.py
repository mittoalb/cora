"""Contract tests for `POST /decisions/{decision_id}/ratings`."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.decision.aggregates.decision import DECISION_RATING_COMMENT_MAX_LENGTH
from cora.decision.errors import UnauthorizedError
from cora.decision.features.rate_decision.route import (
    _get_handler as _get_rate_decision_handler,  # pyright: ignore[reportPrivateUsage]
)


def _register_actor(client: TestClient, name: str = "Operator") -> str:
    """Register an Actor and return its id."""
    r = client.post("/actors", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["actor_id"]


def _register_decision(client: TestClient) -> str:
    """Register a Decision with RunDebrief context for rating tests."""
    actor_id = _register_actor(client, "Decider")
    r = client.post(
        "/decisions",
        json={
            "actor_id": actor_id,
            "context": "RunDebrief",
            "choice": "NominalCompletion",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["decision_id"]


@pytest.mark.contract
def test_post_ratings_returns_204_with_useful() -> None:
    with TestClient(create_app()) as client:
        decision_id = _register_decision(client)
        r = client.post(
            f"/decisions/{decision_id}/ratings",
            json={"rating": "useful"},
        )
    assert r.status_code == 204, r.text


@pytest.mark.contract
def test_post_ratings_returns_204_with_comment() -> None:
    with TestClient(create_app()) as client:
        decision_id = _register_decision(client)
        r = client.post(
            f"/decisions/{decision_id}/ratings",
            json={"rating": "misleading", "comment": "missed the key anomaly"},
        )
    assert r.status_code == 204, r.text


@pytest.mark.contract
@pytest.mark.parametrize("rating", ["useful", "misleading", "ignored"])
def test_post_ratings_accepts_each_rating_value(rating: str) -> None:
    with TestClient(create_app()) as client:
        decision_id = _register_decision(client)
        r = client.post(f"/decisions/{decision_id}/ratings", json={"rating": rating})
    assert r.status_code == 204


@pytest.mark.contract
def test_post_ratings_multiple_from_same_actor_all_succeed() -> None:
    """Multiple ratings from the same caller are allowed (operator
    changing their mind); each one returns 204."""
    with TestClient(create_app()) as client:
        decision_id = _register_decision(client)
        first = client.post(f"/decisions/{decision_id}/ratings", json={"rating": "useful"})
        second = client.post(
            f"/decisions/{decision_id}/ratings",
            json={"rating": "misleading", "comment": "on review"},
        )
    assert first.status_code == 204
    assert second.status_code == 204


@pytest.mark.contract
def test_post_ratings_404_on_unknown_decision() -> None:
    with TestClient(create_app()) as client:
        r = client.post(
            f"/decisions/{uuid4()}/ratings",
            json={"rating": "useful"},
        )
    assert r.status_code == 404


@pytest.mark.contract
def test_post_ratings_422_on_unknown_rating_value() -> None:
    with TestClient(create_app()) as client:
        decision_id = _register_decision(client)
        r = client.post(
            f"/decisions/{decision_id}/ratings",
            json={"rating": "fantastic"},
        )
    assert r.status_code == 422


@pytest.mark.contract
def test_post_ratings_422_on_empty_comment() -> None:
    """Pydantic min_length=1 catches empty comment at the boundary."""
    with TestClient(create_app()) as client:
        decision_id = _register_decision(client)
        r = client.post(
            f"/decisions/{decision_id}/ratings",
            json={"rating": "useful", "comment": ""},
        )
    assert r.status_code == 422


@pytest.mark.contract
def test_post_ratings_422_on_over_cap_comment() -> None:
    with TestClient(create_app()) as client:
        decision_id = _register_decision(client)
        r = client.post(
            f"/decisions/{decision_id}/ratings",
            json={
                "rating": "useful",
                "comment": "x" * (DECISION_RATING_COMMENT_MAX_LENGTH + 1),
            },
        )
    assert r.status_code == 422


@pytest.mark.contract
def test_post_ratings_400_on_whitespace_only_comment() -> None:
    """Whitespace-only comment passes Pydantic min_length=1 but trips
    the domain VO; surfaces as 400."""
    with TestClient(create_app()) as client:
        decision_id = _register_decision(client)
        r = client.post(
            f"/decisions/{decision_id}/ratings",
            json={"rating": "useful", "comment": "   "},
        )
    assert r.status_code == 400


@pytest.mark.contract
def test_post_ratings_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_rate_decision_handler] = lambda: fake_handler
    with TestClient(app) as client:
        r = client.post(
            f"/decisions/{uuid4()}/ratings",
            json={"rating": "useful"},
        )
    assert r.status_code == 403
    assert r.json()["detail"] == "denied for test"
