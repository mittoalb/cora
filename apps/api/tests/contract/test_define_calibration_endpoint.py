"""Contract tests for `POST /calibrations`."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.calibration.aggregates.calibration import CalibrationAlreadyExistsError
from cora.calibration.errors import UnauthorizedError
from cora.calibration.features.define_calibration.route import (
    _get_handler as _get_define_calibration_handler,  # pyright: ignore[reportPrivateUsage]
)


def _body(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "subsystem_or_asset_id": str(uuid4()),
        "quantity": "rotation_center",
        "operating_point": {"energy_keV": 25.0, "optics_config": "5x"},
    }
    base.update(overrides)
    return base


@pytest.mark.contract
def test_post_calibrations_returns_201_with_calibration_id() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/calibrations", json=_body())
    assert response.status_code == 201, response.text
    body = response.json()
    assert "calibration_id" in body
    UUID(body["calibration_id"])


@pytest.mark.contract
def test_post_calibrations_persists_description_when_supplied() -> None:
    with TestClient(create_app()) as client:
        register = client.post(
            "/calibrations",
            json=_body(description="vessel-A bakeout pre-scan"),
        )
        cid = register.json()["calibration_id"]
        get_response = client.get(f"/calibrations/{cid}")
    assert get_response.status_code == 200
    assert get_response.json()["description"] == "vessel-A bakeout pre-scan"


@pytest.mark.contract
def test_post_calibrations_coerces_whitespace_only_description_to_null() -> None:
    """Empty-after-trim → None at the slice boundary (decider convention)."""
    with TestClient(create_app()) as client:
        register = client.post("/calibrations", json=_body(description="    "))
        cid = register.json()["calibration_id"]
        get_response = client.get(f"/calibrations/{cid}")
    assert get_response.json()["description"] is None


@pytest.mark.contract
def test_post_calibrations_accepts_detector_pixel_size_quantity() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/calibrations",
            json=_body(
                quantity="detector_pixel_size",
                operating_point={"optics_config": "10x"},
            ),
        )
    assert response.status_code == 201, response.text


@pytest.mark.contract
def test_post_calibrations_rejects_unknown_quantity_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/calibrations",
            json=_body(quantity="rotation_centre"),  # British spelling, not registered
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_calibrations_rejects_missing_required_operating_point_key_with_400() -> None:
    """rotation_center requires energy_keV + optics_config."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/calibrations",
            json=_body(operating_point={"energy_keV": 25.0}),
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_calibrations_rejects_empty_operating_point_with_400() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/calibrations", json=_body(operating_point={}))
    assert response.status_code == 400


@pytest.mark.contract
def test_post_calibrations_rejects_additional_operating_point_property_with_400() -> None:
    """Q1 lock: `additionalProperties: False` per NXcalibration cautionary tale."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/calibrations",
            json=_body(
                operating_point={
                    "energy_keV": 25.0,
                    "optics_config": "5x",
                    "unknown_field": "drift",
                },
            ),
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_calibrations_rejects_missing_required_body_field_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/calibrations",
            json={
                "subsystem_or_asset_id": str(uuid4()),
                "quantity": "rotation_center",
                # operating_point missing
            },
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_calibrations_rejects_overlong_description_with_422() -> None:
    """Pydantic enforces max_length=2000 BEFORE reaching the decider."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/calibrations",
            json=_body(description="x" * 2001),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_calibrations_rejects_duplicate_identity_with_409() -> None:
    """The projection's jsonb UNIQUE on (subsystem_or_asset_id, quantity,
    operating_point) catches duplicates. Without the deferred lookup-port
    pre-check, the projection-write failure manifests as 409 at the
    operator-facing layer once the projection worker observes the
    duplicate. For the contract layer we simulate via a forced
    CalibrationAlreadyExistsError raise."""
    app = create_app()
    existing_id = uuid4()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise CalibrationAlreadyExistsError(existing_id)

    app.dependency_overrides[_get_define_calibration_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/calibrations", json=_body())
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_calibrations_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_define_calibration_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post("/calibrations", json=_body())
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
