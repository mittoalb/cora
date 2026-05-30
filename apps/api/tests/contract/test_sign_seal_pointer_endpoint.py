"""Contract tests for `POST /federation/seals/{facility_id}/signings`.

The happy-path Live -> Live transition is exercised end-to-end in the
handler tests; here we pin the status-code mappings via dependency
overrides plus Pydantic-layer rejection (missing `new_head_hash`,
empty `new_head_hash`, missing `new_sequence_number`, non-positive
`new_sequence_number`, extra fields under `extra=forbid`, empty
facility path segment).
"""

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.federation.aggregates.seal import (
    SealCannotSignError,
    SealNotFoundError,
    SealSequenceNumberRegressionError,
    SealStatus,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.sign_seal_pointer.route import (
    _get_handler as _get_sign_handler,  # pyright: ignore[reportPrivateUsage]
)

_FACILITY_ID = "aps-2bm"
_NEW_HEAD_HASH = "b" * 64


@pytest.mark.contract
def test_post_sign_seal_pointer_returns_204_via_handler_override() -> None:
    """Handler returns None on the happy path -> route returns 204."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        return None

    app.dependency_overrides[_get_sign_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/signings",
            json={
                "new_head_hash": _NEW_HEAD_HASH,
                "new_sequence_number": 1,
            },
        )
    assert response.status_code == 204, response.text


@pytest.mark.contract
def test_post_sign_seal_pointer_returns_404_on_unknown_facility() -> None:
    """A handler raising SealNotFoundError surfaces as 404."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealNotFoundError("unknown-facility")

    app.dependency_overrides[_get_sign_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/signings",
            json={"new_head_hash": _NEW_HEAD_HASH, "new_sequence_number": 1},
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_sign_seal_pointer_returns_409_when_republishing() -> None:
    """A handler raising SealCannotSignError surfaces as 409 (Republishing)."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealCannotSignError(_FACILITY_ID, SealStatus.REPUBLISHING)

    app.dependency_overrides[_get_sign_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/signings",
            json={"new_head_hash": _NEW_HEAD_HASH, "new_sequence_number": 2},
        )
    assert response.status_code == 409
    assert "cannot sign" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_sign_seal_pointer_returns_422_on_sequence_regression() -> None:
    """A handler raising SealSequenceNumberRegressionError surfaces as 422
    (sequence monotonicity is a schema-shaped invariant; mapped via
    `_handle_unprocessable_error`)."""
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise SealSequenceNumberRegressionError(
            facility_id=_FACILITY_ID,
            prior_sequence_number=5,
            proposed_sequence_number=5,
        )

    app.dependency_overrides[_get_sign_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/signings",
            json={"new_head_hash": _NEW_HEAD_HASH, "new_sequence_number": 5},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_sign_seal_pointer_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_sign_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/signings",
            json={"new_head_hash": _NEW_HEAD_HASH, "new_sequence_number": 1},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"


@pytest.mark.contract
def test_post_sign_seal_pointer_rejects_missing_new_head_hash_with_422() -> None:
    """Pydantic enforces `new_head_hash` presence before reaching the handler."""
    with TestClient(create_app()) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/signings",
            json={"new_sequence_number": 1},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_sign_seal_pointer_rejects_empty_new_head_hash_with_422() -> None:
    """Pydantic min_length=1 enforces non-empty head hash BEFORE reaching the decider."""
    with TestClient(create_app()) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/signings",
            json={"new_head_hash": "", "new_sequence_number": 1},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_sign_seal_pointer_rejects_missing_sequence_number_with_422() -> None:
    """Pydantic enforces `new_sequence_number` presence before reaching the handler."""
    with TestClient(create_app()) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/signings",
            json={"new_head_hash": _NEW_HEAD_HASH},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_sign_seal_pointer_rejects_zero_sequence_number_with_422() -> None:
    """Pydantic ge=1 rejects 0 before reaching the decider."""
    with TestClient(create_app()) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/signings",
            json={"new_head_hash": _NEW_HEAD_HASH, "new_sequence_number": 0},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_sign_seal_pointer_rejects_negative_sequence_number_with_422() -> None:
    """Pydantic ge=1 rejects negative sequence numbers."""
    with TestClient(create_app()) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/signings",
            json={"new_head_hash": _NEW_HEAD_HASH, "new_sequence_number": -1},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_sign_seal_pointer_rejects_extra_field_with_422() -> None:
    """`extra=forbid` on the request body schema rejects unknown fields."""
    with TestClient(create_app()) as client:
        response = client.post(
            f"/federation/seals/{_FACILITY_ID}/signings",
            json={
                "new_head_hash": _NEW_HEAD_HASH,
                "new_sequence_number": 1,
                "unexpected_field": "boom",
            },
        )
    assert response.status_code == 422
