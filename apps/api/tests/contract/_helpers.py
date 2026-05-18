"""Shared test helpers for contract tests against the FastAPI app.

Phase 6l-strict: every POST `/methods` body now requires a
`capability_id` referencing a real Capability stream. Contract
tests use TestClient + a fresh app per test, so each test must
POST `/capabilities` first to create a Capability before POSTing
`/methods`. This helper hides the boilerplate:

    cap_id = create_capability_via_api(client)
    method_id = client.post(
        "/methods",
        json={"name": "M", "needed_families": [], "capability_id": cap_id},
    ).json()["method_id"]

Each call creates a UNIQUE Capability code (uuid-suffixed) so
tests that issue many POSTs to /methods in the same TestClient
session don't collide on the Recipe Capability uniqueness
invariants (none today, but defensive).
"""

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient


def create_capability_via_api(
    client: TestClient,
    *,
    executor_shapes: list[str] | None = None,
    required_affordances: list[str] | None = None,
    headers: dict[str, str] | None = None,
) -> str:
    """POST a fresh Method-shaped Capability, return its UUID string.

    Defaults to `executor_shapes=["Method"]` (the Method-binding
    contract) + empty `required_affordances` (no affordance gating,
    so Plan binding never trips the 6l.B guard for these tests).
    Each call generates a unique `code` suffix so repeated calls
    within one test don't collide.

    `headers` forwards request headers (typically `X-Principal-Id`)
    so tests running under a non-default principal can still seed
    a Capability — the Trust authorize gate requires the principal
    to be in the policy permitted set for `DefineCapability`.
    """
    body: dict[str, Any] = {
        "code": f"cora.capability.contract.test.{uuid4().hex[:12]}",
        "name": "ContractTestCapability",
        "required_affordances": required_affordances or [],
        "executor_shapes": executor_shapes or ["Method"],
    }
    response = client.post("/capabilities", json=body, headers=headers or {})
    if response.status_code != 201:
        raise AssertionError(
            f"create_capability_via_api expected 201, got {response.status_code}: {response.text}"
        )
    return response.json()["capability_id"]


__all__ = ["create_capability_via_api"]
