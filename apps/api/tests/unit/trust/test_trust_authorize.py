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
# Post-3h: handlers pass `UUID(int=0)` (nil sentinel) as conduit_id by
# default; the gating policy must use the same conduit_id to match.
_CONDUIT_ID = UUID(int=0)
_OTHER_CONDUIT_ID = UUID("01900000-0000-7000-8000-00000000aaaa")
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

    result = await authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(result, Allow)


@pytest.mark.unit
async def test_returns_deny_when_principal_not_permitted() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize(_OTHER_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(result, Deny)
    assert "principal" in result.reason.lower()


@pytest.mark.unit
async def test_returns_deny_when_command_not_permitted() -> None:
    store = InMemoryEventStore()
    await _seed_policy(store)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize(_ALLOWED_PRINCIPAL, "DropDatabase", UUID(int=0))
    assert isinstance(result, Deny)
    assert "command" in result.reason.lower()


@pytest.mark.unit
async def test_returns_deny_when_configured_policy_does_not_exist() -> None:
    """Fail-closed: configured policy missing from event store → Deny.
    Pinned because a future change to permissive-on-missing would be a
    significant security regression and must be deliberate."""
    store = InMemoryEventStore()  # nothing seeded
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    result = await authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(result, Deny)
    assert "not found" in result.reason.lower()
    assert str(_POLICY_ID) in result.reason


@pytest.mark.unit
async def test_denies_when_caller_conduit_id_does_not_match_policy() -> None:
    """Phase 3h behavior: TrustAuthorize forwards the caller's
    `conduit_id` to `evaluate`, so a policy bound to one conduit
    denies calls on another. Pinned because this is the whole point
    of 3h — without it the conduit_id parameter on the port shape
    would be cosmetic. (3g had it ignored; 3g's no-op test was
    replaced by this one.)
    """
    store = InMemoryEventStore()
    # Policy governs `_OTHER_CONDUIT_ID`, NOT the nil conduit handlers
    # currently pass.
    await _seed_policy(store, conduit_id=_OTHER_CONDUIT_ID)
    authorize = TrustAuthorize(store, policy_id=_POLICY_ID)

    # Caller passes the nil conduit_id → mismatch → Deny even though
    # principal + command are permitted.
    denied_nil = await authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(denied_nil, Deny)
    assert "conduit" in denied_nil.reason.lower()

    # Caller passes a third, unrelated conduit_id → also Deny.
    third_conduit = UUID("01900000-0000-7000-8000-00000000bbbb")
    denied_other = await authorize(_ALLOWED_PRINCIPAL, "RegisterActor", third_conduit)
    assert isinstance(denied_other, Deny)
    assert "conduit" in denied_other.reason.lower()

    # Caller passes the policy's own conduit_id → Allow (sanity check
    # that conduit-matching is what gates, not some other invariant).
    allowed = await authorize(_ALLOWED_PRINCIPAL, "RegisterActor", _OTHER_CONDUIT_ID)
    assert isinstance(allowed, Allow)


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

    first = await authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(first, Allow)

    # Drop the policy (white-box: InMemoryEventStore exposes its dict).
    store._streams.pop(("Policy", _POLICY_ID))  # type: ignore[attr-defined]  # pyright: ignore[reportUnknownMemberType]

    second = await authorize(_ALLOWED_PRINCIPAL, "RegisterActor", UUID(int=0))
    assert isinstance(second, Deny)
    assert "not found" in second.reason.lower()
