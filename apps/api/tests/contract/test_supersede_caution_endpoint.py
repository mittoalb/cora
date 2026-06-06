"""Contract tests for `POST /cautions/{parent_id}/supersede`."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.caution.errors import UnauthorizedError
from cora.caution.features.supersede_caution.route import (
    _get_handler as _get_supersede_caution_handler,  # pyright: ignore[reportPrivateUsage]
)


def _register_body(asset_id: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "target": {"kind": "Asset", "id": asset_id},
        "category": "Wear",
        "severity": "Caution",
        "text": "original",
        "workaround": "original workaround",
    }
    base.update(overrides)
    return base


def _supersede_body(asset_id: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "target": {"kind": "Asset", "id": asset_id},
        "category": "Wear",
        "severity": "Caution",
        "text": "updated text",
        "workaround": "updated workaround",
    }
    base.update(overrides)
    return base


def _seed_parent(client: TestClient, asset_id: str) -> str:
    response = client.post("/cautions", json=_register_body(asset_id))
    assert response.status_code == 201
    return str(response.json()["caution_id"])


@pytest.mark.contract
def test_post_supersede_returns_201_with_child_caution_id() -> None:
    with TestClient(create_app()) as client:
        asset_id = str(uuid4())
        parent_id = _seed_parent(client, asset_id)
        response = client.post(
            f"/cautions/{parent_id}/supersede",
            json=_supersede_body(asset_id),
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert "caution_id" in body
    assert body["caution_id"] != parent_id


@pytest.mark.contract
def test_post_supersede_returns_404_when_parent_absent() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            f"/cautions/{uuid4()}/supersede",
            json=_supersede_body(str(uuid4())),
        )
    assert response.status_code == 404


@pytest.mark.contract
def test_post_supersede_returns_409_when_parent_already_superseded() -> None:
    with TestClient(create_app()) as client:
        asset_id = str(uuid4())
        parent_id = _seed_parent(client, asset_id)
        first = client.post(
            f"/cautions/{parent_id}/supersede",
            json=_supersede_body(asset_id),
        )
        assert first.status_code == 201
        second = client.post(
            f"/cautions/{parent_id}/supersede",
            json=_supersede_body(asset_id),
        )
    assert second.status_code == 409


@pytest.mark.contract
def test_post_supersede_returns_400_when_target_does_not_match_parent() -> None:
    with TestClient(create_app()) as client:
        asset_id = str(uuid4())
        parent_id = _seed_parent(client, asset_id)
        # Different asset than parent's target.
        other_asset = str(uuid4())
        response = client.post(
            f"/cautions/{parent_id}/supersede",
            json=_supersede_body(other_asset),
        )
    assert response.status_code == 400


@pytest.mark.contract
def test_post_supersede_returns_400_when_workaround_blank() -> None:
    with TestClient(create_app()) as client:
        asset_id = str(uuid4())
        parent_id = _seed_parent(client, asset_id)
        body = _supersede_body(asset_id)
        body["workaround"] = "    "
        response = client.post(f"/cautions/{parent_id}/supersede", json=body)
    assert response.status_code == 400


@pytest.mark.contract
def test_post_supersede_returns_403_when_authorize_denies() -> None:
    app = create_app()

    async def fake_handler(*args: object, **kwargs: object) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("denied for test")

    app.dependency_overrides[_get_supersede_caution_handler] = lambda: fake_handler
    with TestClient(app) as client:
        response = client.post(
            f"/cautions/{uuid4()}/supersede",
            json=_supersede_body(str(uuid4())),
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "denied for test"
