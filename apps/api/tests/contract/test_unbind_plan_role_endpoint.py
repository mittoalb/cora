"""Contract tests for `POST /plans/{plan_id}/unbind-role`.

Sibling of `test_bind_plan_role_endpoint.py`. The shared seed helper
is duplicated as a thin import-and-rebind so the slice-test-coverage
fitness fires the right file-name pin for the unbind slice.
"""

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract.test_bind_plan_role_endpoint import (
    setup_plan_with_role as _setup,
)


def setup_with_binding(client: TestClient) -> dict[str, Any]:
    ctx = _setup(client)
    bound = client.post(
        f"/plans/{ctx['plan_id']}/bind-role",
        json={"role_name": "detector", "asset_id": ctx["asset_id"]},
    )
    assert bound.status_code == 201, bound.text
    return ctx


@pytest.mark.contract
def test_post_unbind_plan_role_returns_204_on_happy_path() -> None:
    with TestClient(create_app()) as client:
        ctx = setup_with_binding(client)
        response = client.post(
            f"/plans/{ctx['plan_id']}/unbind-role",
            json={"role_name": "detector"},
        )
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.contract
def test_post_unbind_plan_role_double_unbind_is_strict_not_idempotent() -> None:
    with TestClient(create_app()) as client:
        ctx = setup_with_binding(client)
        first = client.post(
            f"/plans/{ctx['plan_id']}/unbind-role",
            json={"role_name": "detector"},
        )
        assert first.status_code == 204
        second = client.post(
            f"/plans/{ctx['plan_id']}/unbind-role",
            json={"role_name": "detector"},
        )
    assert second.status_code == 404


@pytest.mark.contract
def test_post_unbind_plan_role_returns_422_for_invalid_role_name_length() -> None:
    with TestClient(create_app()) as client:
        ctx = setup_with_binding(client)
        response = client.post(
            f"/plans/{ctx['plan_id']}/unbind-role",
            json={"role_name": "a" * 51},
        )
    assert response.status_code == 422


@pytest.mark.contract
def test_post_unbind_plan_role_returns_404_for_unknown_plan() -> None:
    unknown = str(uuid4())
    with TestClient(create_app()) as client:
        response = client.post(
            f"/plans/{unknown}/unbind-role",
            json={"role_name": "detector"},
        )
    assert response.status_code == 404
