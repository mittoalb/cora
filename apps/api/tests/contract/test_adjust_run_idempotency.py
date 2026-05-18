"""Contract tests for `Idempotency-Key` support on `POST /runs/{run_id}/adjust`
(Phase 6j).

Same cross-BC `with_idempotency` decorator as other idempotency-wrapped
slices. Idempotency-wrap on the adjust path is the operator-retry
safety net (re-submitting a patch on flaky network must NOT
double-apply).
"""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._subject_helpers import register_active_asset

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _energy_schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": 5,
                "maximum": 50,
                "unit": {"system": "udunits", "code": "keV"},
            }
        },
    }


def _setup_full_run(client: TestClient) -> str:
    cap_id = client.post("/families", json={"name": "FlyMotion"}).json()["family_id"]
    method_id = client.post("/methods", json={"name": "M", "needed_families": [cap_id]}).json()[
        "method_id"
    ]
    r = client.post(
        f"/methods/{method_id}/parameters-schema",
        json={"parameters_schema": _energy_schema()},
    )
    assert r.status_code == 204
    practice_id = client.post(
        "/practices",
        json={"name": "P", "method_id": method_id, "site_id": str(uuid4())},
    ).json()["practice_id"]
    asset_id = client.post(
        "/assets", json={"name": "A", "level": "Enterprise", "parent_id": None}
    ).json()["asset_id"]
    client.post(f"/assets/{asset_id}/add_capability", json={"family_id": cap_id})
    plan_id = client.post(
        "/plans",
        json={"name": "Plan", "practice_id": practice_id, "asset_ids": [asset_id]},
    ).json()["plan_id"]
    client.patch(
        f"/plans/{plan_id}/default-parameters",
        json={"default_parameters_patch": {"energy": 10.0}},
    )
    subject_id = client.post("/subjects", json={"name": "Sample"}).json()["subject_id"]
    mount_asset_id = register_active_asset(client)
    client.post(
        f"/subjects/{subject_id}/mount",
        json={"asset_id": mount_asset_id, "reason": "test"},
    )
    run_id = client.post(
        "/runs",
        json={"name": "32-ID FlyScan", "plan_id": plan_id, "subject_id": subject_id},
    ).json()["run_id"]
    return run_id


@pytest.mark.contract
def test_post_adjust_run_same_key_same_body_returns_cached_204() -> None:
    """Idempotency-wrap: the second call with the same key + same body
    returns 204 without re-applying the patch."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        headers = {"Idempotency-Key": "adj-1"}
        body = {
            "parameter_patch": {"energy": 12.0},
            "reason": "re-center",
        }
        r1 = client.post(f"/runs/{run_id}/adjust", json=body, headers=headers)
        r2 = client.post(f"/runs/{run_id}/adjust", json=body, headers=headers)

    assert r1.status_code == 204, r1.text
    assert r2.status_code == 204, r2.text
    # Effective parameters reflect a SINGLE application of the patch
    # (12.0 once, not 12.0-twice-into-some-other-result).
    get = client.get(f"/runs/{run_id}")
    assert get.json()["effective_parameters"] == {"energy": 12.0}


@pytest.mark.contract
def test_post_adjust_run_same_key_different_body_returns_422() -> None:
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        headers = {"Idempotency-Key": "adj-2"}
        r1 = client.post(
            f"/runs/{run_id}/adjust",
            json={"parameter_patch": {"energy": 12.0}, "reason": "first"},
            headers=headers,
        )
        r2 = client.post(
            f"/runs/{run_id}/adjust",
            json={"parameter_patch": {"energy": 14.0}, "reason": "second"},
            headers=headers,
        )

    assert r1.status_code == 204, r1.text
    assert r2.status_code == 422, r2.text
    body = r2.json()
    assert "idempotency-key" in body["detail"].lower()


@pytest.mark.contract
def test_post_adjust_run_without_key_applies_each_time() -> None:
    """Without a key, each call applies the patch independently. Two
    distinct patch values land as two consecutive RunAdjusted events."""
    with TestClient(create_app()) as client:
        run_id = _setup_full_run(client)
        r1 = client.post(
            f"/runs/{run_id}/adjust",
            json={"parameter_patch": {"energy": 12.0}, "reason": "first"},
        )
        r2 = client.post(
            f"/runs/{run_id}/adjust",
            json={"parameter_patch": {"energy": 14.0}, "reason": "second"},
        )

    assert r1.status_code == 204
    assert r2.status_code == 204
    get = client.get(f"/runs/{run_id}")
    # Last patch wins on effective_parameters; both events on the stream.
    assert get.json()["effective_parameters"] == {"energy": 14.0}
