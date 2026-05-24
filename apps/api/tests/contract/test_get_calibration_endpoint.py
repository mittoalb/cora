"""Contract tests for `GET /calibrations/{calibration_id}`."""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.calibration.errors import UnauthorizedError
from cora.calibration.features.get_calibration.route import (
    _get_handler as _get_get_calibration_handler,  # pyright: ignore[reportPrivateUsage]
)


def _seed(client: TestClient, **overrides: object) -> tuple[str, dict[str, Any]]:
    body: dict[str, Any] = {
        "target_id": str(uuid4()),
        "quantity": "rotation_center",
        "operating_point": {"energy": 25.0, "optics_config": "5x"},
        "description": "vessel-A bakeout pre-scan",
    }
    body.update(overrides)
    response = client.post("/calibrations", json=body)
    assert response.status_code == 201, response.text
    return str(response.json()["calibration_id"]), body


@pytest.mark.contract
def test_get_calibrations_returns_200_with_full_state() -> None:
    with TestClient(create_app()) as client:
        cid, seeded = _seed(client)
        response = client.get(f"/calibrations/{cid}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == cid
    assert body["target_id"] == seeded["target_id"]
    assert body["quantity"] == "rotation_center"
    assert body["operating_point"] == seeded["operating_point"]
    assert body["description"] == seeded["description"]
    assert body["revisions"] == []  # genesis only


@pytest.mark.contract
def test_get_calibrations_returns_404_when_not_found() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/calibrations/{uuid4()}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.contract
def test_get_calibrations_returns_422_for_malformed_uuid_path_param() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/calibrations/not-a-uuid")
    assert response.status_code == 422


@pytest.mark.contract
def test_get_calibrations_reflects_appended_revisions() -> None:
    """The full state response includes every appended revision in order."""
    with TestClient(create_app()) as client:
        cid, _ = _seed(client)
        # Append a Measured revision
        append1 = client.post(
            f"/calibrations/{cid}/revisions",
            json={
                "value": {"center": 1024.5},
                "status": "Provisional",
                "source": {"kind": "Measured", "procedure_id": str(uuid4())},
            },
        )
        rev1_id = append1.json()["revision_id"]
        # Append a Computed revision that supersedes the first
        append2 = client.post(
            f"/calibrations/{cid}/revisions",
            json={
                "value": {"center": 1023.8, "uncertainty": 0.1},
                "status": "Verified",
                "source": {"kind": "Computed", "dataset_id": str(uuid4())},
                "supersedes_revision_id": rev1_id,
            },
        )
        rev2_id = append2.json()["revision_id"]
        response = client.get(f"/calibrations/{cid}")

    body = response.json()
    assert len(body["revisions"]) == 2
    assert body["revisions"][0]["revision_id"] == rev1_id
    assert body["revisions"][0]["status"] == "Provisional"
    assert body["revisions"][0]["source"]["kind"] == "Measured"
    assert body["revisions"][1]["revision_id"] == rev2_id
    assert body["revisions"][1]["status"] == "Verified"
    assert body["revisions"][1]["source"]["kind"] == "Computed"
    assert body["revisions"][1]["supersedes_revision_id"] == rev1_id


@pytest.mark.contract
def test_get_calibrations_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> None:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_get_calibration_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.get(f"/calibrations/{uuid4()}")
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
