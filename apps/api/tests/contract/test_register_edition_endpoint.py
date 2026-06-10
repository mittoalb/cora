"""Contract tests for `POST /editions`.

Genesis create-style endpoint. Body carries kind/title/dataset_ids/
creators + optional license/publication_year/publisher_facility_code.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


def _register_dataset(client: TestClient) -> str:
    response = client.post(
        "/datasets",
        json={
            "name": "parent-dataset",
            "uri": "s3://aps-32id/runs/abc/recon.h5",
            "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
            "byte_size": 1024,
            "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["dataset_id"]


def _good_body(
    *,
    dataset_ids: list[str] | None = None,
    **overrides: object,
) -> dict[str, object]:
    base: dict[str, object] = {
        "kind": "ROCrate",
        "title": "Edition Title",
        "dataset_ids": [str(uuid4())] if dataset_ids is None else dataset_ids,
        "creators": [
            {
                "actor_id": str(uuid4()),
                "affiliation": "ANL",
            }
        ],
    }
    base.update(overrides)
    return base


# ---------- Happy ----------


@pytest.mark.contract
def test_post_editions_returns_201_on_success() -> None:
    with TestClient(create_app()) as client:
        dataset_id = _register_dataset(client)
        response = client.post(
            "/editions",
            json=_good_body(dataset_ids=[dataset_id]),
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert "edition_id" in body


# ---------- Cross-aggregate not-found (404) ----------


@pytest.mark.contract
def test_post_editions_returns_404_when_dataset_id_does_not_exist() -> None:
    """Missing member Dataset surfaces as DatasetNotFoundError -> 404."""
    missing = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            "/editions",
            json=_good_body(dataset_ids=[missing]),
        )
    assert response.status_code == 404
    assert missing in response.json()["detail"]


# ---------- Schema validation (422) ----------


@pytest.mark.contract
def test_post_editions_rejects_unknown_kind_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/editions",
            json=_good_body(kind="JunkKind"),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_editions_rejects_empty_dataset_ids_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/editions",
            json=_good_body(dataset_ids=[]),
        )
    assert response.status_code == 422, response.text


@pytest.mark.contract
def test_post_editions_rejects_empty_creators_with_422() -> None:
    with TestClient(create_app()) as client:
        body = _good_body()
        body["creators"] = []
        response = client.post("/editions", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_editions_rejects_extra_fields_with_422() -> None:
    with TestClient(create_app()) as client:
        body = _good_body()
        body["extra_field"] = "boom"
        response = client.post("/editions", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_editions_rejects_invalid_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/editions",
            json=_good_body(dataset_ids=["not-a-uuid"]),
        )
    assert response.status_code == 422
