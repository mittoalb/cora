"""Cross-principal BOLA contract test.

OWASP API Top 10 #1 is Broken Object-Level Authorization (BOLA):
the API authenticates the caller but doesn't gate the operation
on the *resource* the caller is trying to touch. The classic
failure mode is "principal P1 creates resource R; principal P2
issues GET /resource/<R> and reads it".

CORA's day-1 defense is the Trust BC's `permitted_principals` x
`permitted_commands` policy: when `TrustAuthorize` is wired with
a real policy, every command is gated by `(principal_id,
command_name)`. This test pins the load-bearing chain end-to-end
across multiple BCs to prove the gating actually fires for cross-
principal reads, not just create-style writes (BOLA's most common
exposure surface is reads).

This test does NOT exercise per-resource ownership (ReBAC); see
`memory/project_authz_future.md` for that planned phase. What it
DOES prove today: a deployment that turns on TrustAuthorize and
configures `permitted_principals` correctly cannot leak a P1
aggregate to a P2 read just because both are authenticated, even
when both have valid X-Principal-Id headers.

Parametrized across the most BOLA-exposed BCs (Access, Subject,
Equipment) — each runs the same shape: P1 creates, P2 reads,
expect 403. Adding a new BC to the parametrization is a one-line
change.
"""

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false

import asyncio
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cora.api.main import create_app
from cora.equipment.aggregates.asset import AssetLevel
from cora.infrastructure.event_envelope import to_new_event
from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    event_type_name,
    to_payload,
)


def _seed_policy(
    app: FastAPI,
    *,
    policy_id: UUID,
    permitted_principal: UUID,
    permitted_commands: frozenset[str],
) -> None:
    """Seed a single PolicyDefined event into the running app's
    in-memory store. Same shape as `test_principal_header.py`'s
    helper; duplicated here to keep the BOLA test self-contained
    rather than coupling two files via a shared fixture file."""
    event = PolicyDefined(
        policy_id=policy_id,
        name="Bola-test-policy",
        conduit_id=UUID(int=0),
        permitted_principals=[permitted_principal],
        permitted_commands=list(permitted_commands),
        occurred_at=datetime.now(tz=UTC),
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=uuid4(),
        command_name="DefinePolicy",
        correlation_id=uuid4(),
    )
    asyncio.run(
        app.state.deps.event_store.append("Policy", policy_id, 0, [new_event]),
    )


@pytest.fixture
def bola_app(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, UUID, UUID]]:
    """Spin up an app with `TrustAuthorize` wired against a policy
    that permits ONE principal (P1) to issue every command this test
    exercises. P2 is any other UUID; the policy denies it implicitly.

    Yields (client, p1, p2).
    """
    policy_id = UUID("01900000-0000-7000-8000-00000000bb01")
    p1 = UUID("01900000-0000-7000-8000-00000000bb11")
    p2 = UUID("01900000-0000-7000-8000-00000000bb12")

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("TRUST_POLICY_ID", str(policy_id))

    client = TestClient(create_app())
    client.__enter__()  # start lifespan; app.state.deps populated

    _seed_policy(
        cast("FastAPI", client.app),
        policy_id=policy_id,
        permitted_principal=p1,
        permitted_commands=frozenset(
            {
                # Create-side
                "RegisterActor",
                "RegisterSubject",
                "RegisterAsset",
                # Read-side (the gates this test exercises)
                "GetActor",
                "GetSubject",
                "GetAsset",
                # List-side (8e-1c)
                "ListActors",
            }
        ),
    )
    try:
        yield client, p1, p2
    finally:
        client.__exit__(None, None, None)


def _create_actor_as(client: TestClient, principal: UUID) -> UUID:
    response = client.post(
        "/actors",
        json={"name": "P1's actor"},
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["actor_id"])


def _create_subject_as(client: TestClient, principal: UUID) -> UUID:
    response = client.post(
        "/subjects",
        json={"name": "P1's subject"},
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["subject_id"])


def _create_asset_as(client: TestClient, principal: UUID) -> UUID:
    response = client.post(
        "/assets",
        json={
            "name": "P1's asset",
            "level": AssetLevel.ENTERPRISE.value,
            "parent_id": None,
        },
        headers={"X-Principal-Id": str(principal)},
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["asset_id"])


CreateFn = Callable[[TestClient, UUID], UUID]
"""Shape of a BOLA-scenario factory: takes the test client and the
principal to create-as, returns the new aggregate's id."""


_BOLA_SCENARIOS = [
    pytest.param(_create_actor_as, "/actors", id="access:actor"),
    pytest.param(_create_subject_as, "/subjects", id="subject:subject"),
    pytest.param(_create_asset_as, "/assets", id="equipment:asset"),
]


@pytest.mark.contract
@pytest.mark.parametrize(("create_fn", "read_path_prefix"), _BOLA_SCENARIOS)
def test_p2_cannot_read_p1s_aggregate_when_policy_gates_principal(
    bola_app: tuple[TestClient, UUID, UUID],
    create_fn: CreateFn,
    read_path_prefix: str,
) -> None:
    """P1 (permitted) creates an aggregate; P2 (not permitted) tries
    to read it. The policy denies P2 -> 403 from the read endpoint.
    Pin: cross-principal reads are gated even when both principals
    are authenticated."""
    client, p1, p2 = bola_app

    aggregate_id = create_fn(client, p1)

    # P2 attempts to read the resource P1 just created.
    response = client.get(
        f"{read_path_prefix}/{aggregate_id}",
        headers={"X-Principal-Id": str(p2)},
    )
    assert response.status_code == 403, (
        f"BOLA gap: P2 was able to read P1's aggregate at "
        f"{read_path_prefix}/{aggregate_id} (status={response.status_code}, "
        f"body={response.text}). The policy permits only P1; this "
        f"read should have been denied."
    )


@pytest.mark.contract
@pytest.mark.parametrize(("create_fn", "read_path_prefix"), _BOLA_SCENARIOS)
def test_p1_can_still_read_their_own_aggregate(
    bola_app: tuple[TestClient, UUID, UUID],
    create_fn: CreateFn,
    read_path_prefix: str,
) -> None:
    """Inverse sanity: the gate is per-principal, not blanket-deny.
    P1 (permitted) reads their own resource and gets 200."""
    client, p1, _ = bola_app

    aggregate_id = create_fn(client, p1)

    response = client.get(
        f"{read_path_prefix}/{aggregate_id}",
        headers={"X-Principal-Id": str(p1)},
    )
    assert response.status_code == 200, (
        f"P1 was unexpectedly denied reading their own aggregate "
        f"({response.status_code}, {response.text}). Policy/permitted-"
        f"commands setup is wrong."
    )


# ---------- List endpoint BOLA (weaker, command-level only today) ----------


@pytest.mark.contract
def test_p2_cannot_call_list_actors_when_command_not_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    """List-endpoint BOLA defense at TODAY's granularity: the
    `ListActors` command is gated by Trust policy. P2 isn't in
    `permitted_principals` so the command itself is denied with 403
    before the projection table is queried.

    This is the WEAKER assertion than per-row BOLA (P2 sees zero of
    P1's items in the response body) — see `project_deferred.md`
    entry "BOLA per-row scoping for list endpoints (ReBAC dependency)".
    Today the projection has no per-principal scoping, so once
    ListActors IS permitted to a principal, that principal sees
    every actor regardless of who created them. The honest test
    pins the defense that DOES exist.
    """
    client, _, p2 = bola_app

    response = client.get("/actors", headers={"X-Principal-Id": str(p2)})
    assert response.status_code == 403, (
        f"P2 should be denied ListActors at the command level "
        f"(status={response.status_code}, body={response.text})."
    )


@pytest.mark.contract
def test_p1_can_call_list_actors_when_command_permitted(
    bola_app: tuple[TestClient, UUID, UUID],
) -> None:
    """Inverse: the gate is per-principal, not blanket-deny."""
    client, p1, _ = bola_app

    response = client.get("/actors", headers={"X-Principal-Id": str(p1)})
    assert response.status_code == 200, (
        f"P1 should be permitted ListActors (status={response.status_code}, body={response.text})."
    )
