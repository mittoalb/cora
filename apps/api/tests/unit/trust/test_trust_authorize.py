"""Unit tests for the `TrustAuthorize` adapter.

Exercises the adapter against `InMemoryEventStore` with a seeded
PolicyDefined event. The adapter is the production path that gates
every cross-BC command through a single configured Policy.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.ports import Allow, Deny
from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    event_type_name,
    to_payload,
)
from cora.trust.authorize import TrustAuthorize

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_POLICY_ID = UUID("01900000-0000-7000-8000-000000000601")
_CONDUIT_ID = UUID("01900000-0000-7000-8000-00000000aaaa")
_ALLOWED_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a01")
_OTHER_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a02")


async def _seed_policy(
    store: InMemoryEventStore,
    *,
    policy_id: UUID = _POLICY_ID,
    conduit_id: UUID = _CONDUIT_ID,
    principals: frozenset[UUID] = frozenset({_ALLOWED_PRINCIPAL}),
    commands: frozenset[str] = frozenset({"RegisterActor"}),
) -> None:
    event = PolicyDefined(
        policy_id=policy_id,
        name="Test-policy",
        conduit_id=conduit_id,
        permitted_principals=list(principals),
        permitted_commands=list(commands),
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=uuid4(),
        command_name="DefinePolicy",
        correlation_id=uuid4(),
    )
    await store.append("Policy", policy_id, expected_version=0, events=[new_event])


@pytest.mark.unit
async def test_returns_allow_when_subject_matches_configured_policy() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize(_ALLOWED_PRINCIPAL, "RegisterActor", "default")
    assert isinstance(result, Allow)


@pytest.mark.unit
async def test_returns_deny_when_principal_not_permitted() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize(_OTHER_PRINCIPAL, "RegisterActor", "default")
    assert isinstance(result, Deny)
    assert "principal" in result.reason.lower()


@pytest.mark.unit
async def test_returns_deny_when_command_not_permitted() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize(_ALLOWED_PRINCIPAL, "DropDatabase", "default")
    assert isinstance(result, Deny)
    assert "command" in result.reason.lower()


@pytest.mark.unit
async def test_returns_deny_when_configured_policy_does_not_exist() -> None:
    """Fail-closed: configured policy missing from event store → Deny.
    Pinned because a future change to permissive-on-missing would be a
    significant security regression and must be deliberate."""
    store = InMemoryEventStore()  # nothing seeded
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize(_ALLOWED_PRINCIPAL, "RegisterActor", "default")
    assert isinstance(result, Deny)
    assert "not found" in result.reason.lower()
    assert str(_POLICY_ID) in result.reason


@pytest.mark.unit
async def test_ignores_caller_supplied_conduit_string() -> None:
    """Phase 3e behavior: the caller's `conduit` string parameter is
    ignored; the configured policy's own `conduit_id` is what
    `evaluate` checks. Pin so a future port-shape change to
    `conduit_id: UUID` has to flip this."""
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    # Caller passes a wildly different conduit string — should not affect outcome.
    result_default = await authorize(_ALLOWED_PRINCIPAL, "RegisterActor", "default")
    result_other = await authorize(_ALLOWED_PRINCIPAL, "RegisterActor", "any-other-conduit-string")
    result_empty = await authorize(_ALLOWED_PRINCIPAL, "RegisterActor", "")

    assert isinstance(result_default, Allow)
    assert isinstance(result_other, Allow)
    assert isinstance(result_empty, Allow)


@pytest.mark.unit
async def test_loads_policy_on_each_call_no_caching() -> None:
    """Pin the no-caching contract: changing the policy in the store
    between calls is reflected on the very next call. (Future caching
    + LISTEN/NOTIFY invalidation would change this; should be a
    deliberate change.)

    Reseeding is awkward here (PolicyDefined is genesis-only); instead
    we verify the load happens by deleting the seeded event and
    showing the next call returns Deny rather than the previously-
    loaded Allow.
    """
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    first = await authorize(_ALLOWED_PRINCIPAL, "RegisterActor", "default")
    assert isinstance(first, Allow)

    # Drop the policy (white-box: InMemoryEventStore exposes its dict).
    store._streams.pop(("Policy", _POLICY_ID))  # type: ignore[attr-defined]  # pyright: ignore[reportUnknownMemberType]

    second = await authorize(_ALLOWED_PRINCIPAL, "RegisterActor", "default")
    assert isinstance(second, Deny)
    assert "not found" in second.reason.lower()
