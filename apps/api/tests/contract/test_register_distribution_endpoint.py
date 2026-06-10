"""Contract tests for `POST /distributions`.

Genesis create-style endpoint mirroring `POST /datasets` shape.
Body carries cross-aggregate refs (dataset_id same-BC, supply_id
cross-BC), addressing (uri + access_protocol), and the byte-identical-
copy invariants (checksum + byte_size + encoding).

## Scope

In a TestClient app the cross-BC `SupplyLookup` adapter is the
default `AllSatisfiedSupplyLookup` stub (no postgres pool, no
projection worker), so the lookup-by-id branch returns None on
every call. The happy path (201) is locked in
`tests/integration/test_register_distribution_handler_postgres.py`
where `PostgresSupplyLookup` against `proj_supply_summary` is wired
in. These contract tests focus on the wire-shape, schema validation,
and the error-mapping branches that DO surface in TestClient:

  - 400: domain-VO validation (URI scheme missing).
  - 404: dataset_id not in event store (same-BC pre-load fails); and
         supply_id never resolves under the default stub.
  - 422: Pydantic shape failures (unknown access_protocol, negative
         byte_size, extra fields).

The route's response_model + error_responses metadata is also
exercised via the OpenAPI snapshot pinned in
`test_committed_openapi_snapshot_matches_live_spec`.
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
    dataset_id: str | None = None,
    supply_id: str | None = None,
    **overrides: object,
) -> dict[str, object]:
    base: dict[str, object] = {
        "dataset_id": dataset_id or str(uuid4()),
        "supply_id": supply_id or str(uuid4()),
        "uri": "s3://aps-32id/runs/abc/recon.h5",
        "checksum": {"algorithm": "sha256", "value": _GOOD_SHA256},
        "byte_size": 1024,
        "encoding": {"media_type": "application/x-hdf5", "conforms_to": []},
        "access_protocol": "S3",
    }
    base.update(overrides)
    return base


# ---------- Cross-aggregate not-found (404) ----------


@pytest.mark.contract
def test_post_distributions_returns_404_when_dataset_id_does_not_exist() -> None:
    """Same-BC Dataset pre-load fails -> DatasetNotFoundError -> 404."""
    missing_dataset = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            "/distributions",
            json=_good_body(dataset_id=missing_dataset),
        )
    assert response.status_code == 404
    assert missing_dataset in response.json()["detail"]


@pytest.mark.contract
def test_post_distributions_returns_404_when_supply_lookup_returns_none() -> None:
    """Cross-BC SupplyLookup returns None under the default test stub ->
    DistributionSupplyNotFoundError -> 404."""
    with TestClient(create_app()) as client:
        dataset_id = _register_dataset(client)
        supply_id = str(uuid4())
        response = client.post(
            "/distributions",
            json=_good_body(dataset_id=dataset_id, supply_id=supply_id),
        )
    assert response.status_code == 404
    assert supply_id in response.json()["detail"]


# Note: decider VO validation (400) cannot be reached in TestClient
# because the handler pre-loads Dataset + Supply before calling the
# decider; the default AllSatisfiedSupplyLookup stub returns None,
# so the cross-BC 404 fires first. The decider VO branches are
# locked at the unit tier (tests/unit/data/test_register_distribution_decider.py
# + test_distribution_state.py) and the integration tier
# (test_register_distribution_handler_postgres.py via PostgresSupplyLookup).


# ---------- Schema validation (422) ----------


@pytest.mark.contract
def test_post_distributions_rejects_unknown_access_protocol_with_422() -> None:
    """Closed AccessProtocol enum at the Pydantic boundary."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/distributions",
            json=_good_body(access_protocol="FTP"),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_distributions_rejects_extra_fields_with_422() -> None:
    """Pydantic model_config={'extra': 'forbid'} rejects unknown keys."""
    with TestClient(create_app()) as client:
        body = _good_body()
        body["extra_field"] = "boom"
        response = client.post("/distributions", json=body)
    assert response.status_code == 422


@pytest.mark.contract
def test_post_distributions_rejects_negative_byte_size_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/distributions",
            json=_good_body(byte_size=-1),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_distributions_rejects_invalid_uuid_with_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/distributions",
            json=_good_body(dataset_id="not-a-uuid"),
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_distributions_rejects_missing_supply_id_with_422() -> None:
    with TestClient(create_app()) as client:
        body = _good_body()
        del body["supply_id"]
        response = client.post("/distributions", json=body)
    assert response.status_code == 422
