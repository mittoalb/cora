"""Contract tests for `POST /federation/seals/{facility_id}/republishing/complete`.

The happy-path Republishing -> Live transition is exercised end-to-
end in the handler tests; here we pin the status-code mappings via
dependency overrides plus Pydantic-layer rejection (extra fields
under `extra=forbid`). The decider's head-pair / no-prior-head
structural invariants now surface as 400 via the typed
InvalidSealHeadHashError. Stage 2c-seal sibling slices ship in the
same change, so the upstream initialize + republishing-start are not
chained here.
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.seal import (
    SealCannotCompleteRepublishingError,
    SealNotFoundError,
    SealSequenceNumberRegressionError,
    SealStatus,
)
from cora.federation.aggregates.seal.state import InvalidSealHeadHashError
from cora.federation.errors import UnauthorizedError
from cora.federation.features.complete_seal_republishing.route import (
    _get_handler as _get_complete_handler,  # pyright: ignore[reportPrivateUsage]
)

_FACILITY_ID = "aps-2bm"


@pytest.mark.contract
def test_post_complete_seal_republishing_returns_204_via_handler_override() -> None:
    """Handler returns None on the happy path -> route returns 204."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/republishing/complete",
            json={
                "new_head_hash": "b" * 64,
                "new_sequence_number": 1,
            },
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_complete_seal_republishing_returns_204_without_body() -> None:
    """Body is optional; omitting it (both pair fields absent) is accepted."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/republishing/complete",
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_complete_seal_republishing_returns_204_with_empty_body() -> None:
    """An explicit empty-object body is also accepted (both fields default None)."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/republishing/complete",
            json={},
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_complete_seal_republishing_returns_404_on_unknown_seal() -> None:
    """A handler raising SealNotFoundError surfaces as 404."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealNotFoundError("unknown-facility")

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/unknown-facility/republishing/complete",
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_complete_seal_republishing_returns_409_when_live() -> None:
    """A handler raising SealCannotCompleteRepublishingError surfaces as 409."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealCannotCompleteRepublishingError(
            facility_id=_FACILITY_ID,
            current_status=SealStatus.LIVE,
        )

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/republishing/complete",
        )
    assert response.status_code == 409
    assert "cannot complete" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_complete_seal_republishing_returns_422_on_sequence_regression() -> None:
    """A handler raising SealSequenceNumberRegressionError surfaces as 422."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealSequenceNumberRegressionError(
            facility_id=_FACILITY_ID,
            prior_sequence_number=5,
            proposed_sequence_number=3,
        )

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/republishing/complete",
            json={"new_head_hash": "b" * 64, "new_sequence_number": 3},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_complete_seal_republishing_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/republishing/complete",
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_complete_seal_republishing_returns_400_on_pair_invariant_violation() -> None:
    """Decider-layer pairing invariant violation surfaces as 400 via
    InvalidSealHeadHashError (sequence-without-head shape)."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise InvalidSealHeadHashError(
            "new_head_hash and new_sequence_number must be supplied "
            "together or omitted together (new_head_hash=None, "
            "new_sequence_number=6)"
        )

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/republishing/complete",
            json={"new_sequence_number": 6},
        )
    assert response.status_code == 400
    assert "head_hash" in response.json()["detail"]


@pytest.mark.contract
def test_post_complete_seal_republishing_returns_400_when_prior_head_missing() -> None:
    """Decider-layer 'no prior head' rejection surfaces as 400 via
    InvalidSealHeadHashError when the body omits the head pair."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise InvalidSealHeadHashError(
            f"Seal for facility {_FACILITY_ID!r}: "
            "complete_seal_republishing without new_head_hash requires "
            "a prior signing (current_head_hash is None)"
        )

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/republishing/complete",
        )
    assert response.status_code == 400
    assert "current_head_hash is None" in response.json()["detail"]


@pytest.mark.contract
def test_post_complete_seal_republishing_rejects_extra_field_with_422() -> None:
    """`extra=forbid` on the request body schema rejects unknown fields."""
    with TestClient(create_app()) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/republishing/complete",
            json={
                "new_head_hash": "b" * 64,
                "new_sequence_number": 1,
                "unexpected_field": "boom",
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_complete_seal_republishing_rejects_non_integer_sequence_with_422() -> None:
    """Pydantic integer coercion failure surfaces as 422."""
    with TestClient(create_app()) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/republishing/complete",
            json={
                "new_head_hash": "b" * 64,
                "new_sequence_number": "not-an-int",
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_complete_seal_republishing_passes_facility_id_to_handler() -> None:
    """The path's `facility_id` reaches the handler as the command field."""
    app = create_app()
    captured: dict[str, object] = {}

    async def fake_handler(command: object, **kwargs: object) -> None:
        _ = kwargs
        captured["command"] = command

    app.dependency_overrides[_get_complete_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            "/federation/seals/aps-35bm/republishing/complete",
        )
    assert response.status_code == 204
    cmd = captured["command"]
    assert cmd.facility_id == "aps-35bm"  # type: ignore[attr-defined]
    assert cmd.new_head_hash is None  # type: ignore[attr-defined]
    assert cmd.new_sequence_number is None  # type: ignore[attr-defined]
