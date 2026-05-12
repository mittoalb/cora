"""Contract tests for `POST /datasets`.

Genesis create-style endpoint mirroring the shape used by every
other register / define endpoint. Body carries nested checksum +
encoding objects, plus the optional cross-aggregate refs.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


def _good_body(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "32-ID FlyScan recon",
        "uri": "s3://aps-32id/runs/abc/recon.h5",
        "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
        "byte_size": 1024,
        "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
    }
    base.update(overrides)
    return base


def _start_run(client: TestClient) -> str:
    """Set up the full upstream chain and start a Run; return the run_id."""
    cap_id = client.post("/capabilities", json={"name": "FlyMotion"}).json()["capability_id"]
    method_id = client.post("/methods", json={"name": "M", "needs_capabilities": [cap_id]}).json()[
        "method_id"
    ]
    practice_id = client.post(
        "/practices",
        json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets", json={"name": "A", "level": "Enterprise", "parent_id": None}
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add_capability", json={"capability_id": cap_id})
    plan_id = client.post(
        "/plans",
        json={"name": "Plan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    client.post(f"/subjects/{subject_id}/mount")
    run_id = client.post(
        "/runs",
        json={"name": "32-ID FlyScan", "plan_id": plan_id, "subject_id": subject_id},
    ).json()["run_id"]
    return run_id


def _register_subject(client: TestClient) -> str:
    return client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]


# ---------- Happy path ----------


@pytest.mark.contract
def test_post_datasets_returns_201_and_dataset_id_for_minimal_body() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body())
    assert response.status_code == 201
    body = response.json()
    assert "dataset_id" in body


@pytest.mark.contract
def test_post_datasets_round_trips_into_get_dataset_response() -> None:
    with TestClient(create_app()) as client:
        create = client.post(
            "/datasets",
            json=_good_body(
                encoding={
                    "media_type": "application/x-hdf5",
                    "conforms_to": [
                        "https://manual.nexusformat.org/",
                        "https://example.com/profile",
                    ],
                },
            ),
        )
        assert create.status_code == 201
        dataset_id = create.json()["dataset_id"]
        get = client.get(f"/datasets/{dataset_id}")
    assert get.status_code == 200
    body = get.json()
    assert body["id"] == dataset_id
    assert body["name"] == "32-ID FlyScan recon"
    assert body["uri"] == "s3://aps-32id/runs/abc/recon.h5"
    assert body["checksum"]["algorithm"] == "sha256"
    assert body["checksum"]["value"] == _GOOD_SHA256
    assert body["byte_size"] == 1024
    assert body["encoding"]["media_type"] == "application/x-hdf5"
    # Wire-shape conforms_to is sorted (canonical).
    assert body["encoding"]["conforms_to"] == [
        "https://example.com/profile",
        "https://manual.nexusformat.org/",
    ]
    assert body["producing_run_id"] is None
    assert body["subject_id"] is None
    assert body["derived_from"] == []
    assert body["status"] == "Registered"


@pytest.mark.contract
def test_post_datasets_with_producing_run_id_links_through() -> None:
    with TestClient(create_app()) as client:
        run_id = _start_run(client)
        response = client.post("/datasets", json=_good_body(producing_run_id=run_id))
    assert response.status_code == 201


@pytest.mark.contract
def test_post_datasets_with_subject_id_links_through() -> None:
    with TestClient(create_app()) as client:
        subject_id = _register_subject(client)
        response = client.post("/datasets", json=_good_body(subject_id=subject_id))
    assert response.status_code == 201


@pytest.mark.contract
def test_post_datasets_with_derived_from_links_through() -> None:
    with TestClient(create_app()) as client:
        upstream = client.post("/datasets", json=_good_body()).json()["dataset_id"]
        response = client.post("/datasets", json=_good_body(derived_from=[upstream]))
    assert response.status_code == 201


# ---------- Cross-aggregate not-found (409) ----------


@pytest.mark.contract
def test_post_datasets_returns_409_when_producing_run_id_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(producing_run_id=missing_id))
    assert response.status_code == 409
    assert "producing_run_id" in response.json()["detail"]


@pytest.mark.contract
def test_post_datasets_returns_409_when_subject_id_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(subject_id=missing_id))
    assert response.status_code == 409
    assert "subject_id" in response.json()["detail"]


@pytest.mark.contract
def test_post_datasets_returns_409_when_derived_from_id_does_not_exist() -> None:
    missing_id = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(derived_from=[missing_id]))
    assert response.status_code == 409
    assert missing_id in response.json()["detail"]


# ---------- Schema / domain validation ----------


@pytest.mark.contract
def test_post_datasets_rejects_empty_name_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(name=""))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_datasets_rejects_whitespace_only_name_with_400() -> None:
    """Whitespace passes Pydantic but the decider trims and rejects."""
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(name="   "))
    assert response.status_code == 400
    assert "name" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_datasets_rejects_negative_byte_size_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(byte_size=-1))
    assert response.status_code == 422


@pytest.mark.contract
def test_post_datasets_rejects_unsupported_checksum_algorithm_with_400() -> None:
    """Algorithm passes Pydantic shape but decider rejects non-sha256."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/datasets",
            json=_good_body(checksum={"algorithm": "md5", "value": "d" * 32}),
        )
    assert response.status_code == 400
    assert "sha256" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_datasets_rejects_uri_without_scheme_with_400() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(uri="just-a-path"))
    assert response.status_code == 400
    assert "scheme" in response.json()["detail"].lower()


@pytest.mark.contract
@pytest.mark.parametrize(
    "uri",
    [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
    ],
)
def test_post_datasets_rejects_known_xss_uri_schemes_with_400(uri: str) -> None:
    """Defensive blocklist applied at the API boundary. Pure blocklist
    so we don't constrain real storage schemes."""
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json=_good_body(uri=uri))
    assert response.status_code == 400
    assert "blocked" in response.json()["detail"].lower()


@pytest.mark.contract
def test_post_datasets_rejects_extra_fields_with_422() -> None:
    """Pydantic model_config={'extra': 'forbid'} rejects unknown keys."""
    with TestClient(create_app()) as client:
        response = client.post("/datasets", json={**_good_body(), "extra_field": "boom"})
    assert response.status_code == 422


# ---------- GET ----------


@pytest.mark.contract
def test_get_datasets_returns_404_for_unknown_id() -> None:
    with TestClient(create_app()) as client:
        response = client.get(f"/datasets/{uuid4()}")
    assert response.status_code == 404


@pytest.mark.contract
def test_get_datasets_rejects_invalid_path_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/datasets/not-a-uuid")
    assert response.status_code == 422
