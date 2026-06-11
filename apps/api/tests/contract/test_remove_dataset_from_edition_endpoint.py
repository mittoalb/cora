"""Contract tests for `DELETE /editions/{edition_id}/datasets/{dataset_id}`.

Strict-not-idempotent removal: returns 204 on success, 404 when the
Edition is missing or the Dataset is not a member, 409 when the
Edition is not in Registered state or removing the last member.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


def _register_dataset(client: TestClient, *, name: str = "ds") -> str:
    response = client.post(
        "/datasets",
        json={
            "name": name,
            "uri": f"s3://b/{name}",
            "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
            "byte_size": 1024,
            "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["dataset_id"]


def _register_edition(client: TestClient, *, dataset_ids: list[str]) -> str:
    response = client.post(
        "/editions",
        json={
            "kind": "ROCrate",
            "title": "Edition Title",
            "dataset_ids": dataset_ids,
            "creators": [
                {"actor_id": str(uuid4()), "affiliation": "ANL"},
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["edition_id"]


# ---------- Happy ----------


@pytest.mark.contract
def test_delete_edition_dataset_returns_204_on_success() -> None:
    with TestClient(create_app()) as client:
        first = _register_dataset(client, name="first")
        second = _register_dataset(client, name="second")
        edition_id = _register_edition(client, dataset_ids=[first, second])
        response = client.delete(f"/editions/{edition_id}/datasets/{first}")
    assert response.status_code == 204
    assert response.content == b""


# ---------- 404 ----------


@pytest.mark.contract
def test_delete_edition_dataset_returns_404_for_unknown_edition() -> None:
    with TestClient(create_app()) as client:
        unknown_edition = uuid4()
        response = client.delete(f"/editions/{unknown_edition}/datasets/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.contract
def test_delete_edition_dataset_returns_404_when_not_member() -> None:
    with TestClient(create_app()) as client:
        first = _register_dataset(client, name="first")
        edition_id = _register_edition(client, dataset_ids=[first])
        non_member = _register_dataset(client, name="non-member")
        response = client.delete(f"/editions/{edition_id}/datasets/{non_member}")
    assert response.status_code == 404


# ---------- 409 ----------


@pytest.mark.contract
def test_delete_edition_dataset_returns_409_when_removing_last() -> None:
    with TestClient(create_app()) as client:
        only = _register_dataset(client, name="only")
        edition_id = _register_edition(client, dataset_ids=[only])
        response = client.delete(f"/editions/{edition_id}/datasets/{only}")
    assert response.status_code == 409


# ---------- 422 ----------


@pytest.mark.contract
def test_delete_edition_dataset_rejects_malformed_path_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.delete(f"/editions/not-a-uuid/datasets/{uuid4()}")
    assert response.status_code == 422
