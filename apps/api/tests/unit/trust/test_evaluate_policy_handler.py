"""Unit tests for the `evaluate_policy` query handler."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.config import Settings
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import (
    Allow,
    AllowAllAuthorize,
    AuthzResult,
    Deny,
    FixedIdGenerator,
    FrozenClock,
)
from cora.trust import TrustHandlers, UnauthorizedError, wire_trust
from cora.trust.aggregates.policy.events import (
    PolicyDefined,
    event_type_name,
    to_payload,
)
from cora.trust.features import evaluate_policy
from cora.trust.features.evaluate_policy import EvaluatePolicy

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_POLICY_ID = UUID("01900000-0000-7000-8000-000000000501")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CONDUIT_ID = UUID("01900000-0000-7000-8000-00000000aaaa")
_OTHER_CONDUIT = UUID("01900000-0000-7000-8000-00000000bbbb")
_ALLOWED_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a01")
_OTHER_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a02")


class DenyAllAuthorize:
    """Authorize stub that denies every command."""

    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
    ) -> AuthzResult:
        _ = (principal_id, command_name, conduit_id)
        return Deny(reason="denied for test")


def _build_deps(
    *,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    settings = Settings(app_env="test")  # type: ignore[call-arg]
    # Sequence has plenty of ids for any seeding the test does;
    # evaluate_policy itself doesn't consume id_generator.
    return Kernel(
        settings=settings,
        clock=FrozenClock(_NOW),
        id_generator=FixedIdGenerator([uuid4() for _ in range(8)]),
        authorize=DenyAllAuthorize() if deny else AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
    )


async def _seed_policy(
    store: InMemoryEventStore,
    *,
    policy_id: UUID = _POLICY_ID,
    conduit_id: UUID = _CONDUIT_ID,
    principals: frozenset[UUID] = frozenset({_ALLOWED_PRINCIPAL}),
    commands: frozenset[str] = frozenset({"RegisterActor"}),
) -> None:
    """Seed the event store with a single PolicyDefined event.

    Bypasses define_policy so the test exercises only evaluate_policy's
    load-and-evaluate path (define_policy has its own unit tests).
    """
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
        principal_id=uuid4(),
    )
    await store.append("Policy", policy_id, expected_version=0, events=[new_event])


def _query(
    *,
    policy_id: UUID = _POLICY_ID,
    evaluated_principal_id: UUID = _ALLOWED_PRINCIPAL,
    evaluated_command_name: str = "RegisterActor",
    evaluated_conduit_id: UUID = _CONDUIT_ID,
) -> EvaluatePolicy:
    return EvaluatePolicy(
        policy_id=policy_id,
        evaluated_principal_id=evaluated_principal_id,
        evaluated_command_name=evaluated_command_name,
        evaluated_conduit_id=evaluated_conduit_id,
    )


@pytest.mark.unit
async def test_handler_returns_none_when_policy_does_not_exist() -> None:
    """Missing policy → handler returns None (route layer maps to 404)."""
    deps = _build_deps()
    handler = evaluate_policy.bind(deps)

    result = await handler(
        _query(policy_id=uuid4()),  # nothing seeded for this id
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result is None


@pytest.mark.unit
async def test_handler_returns_allow_when_subject_matches_policy() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_policy(store)
    handler = evaluate_policy.bind(deps)

    result = await handler(
        _query(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(result, Allow)


@pytest.mark.unit
async def test_handler_returns_deny_when_principal_not_permitted() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_policy(store)
    handler = evaluate_policy.bind(deps)

    result = await handler(
        _query(evaluated_principal_id=_OTHER_PRINCIPAL),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(result, Deny)
    assert "principal" in result.reason.lower()


@pytest.mark.unit
async def test_handler_returns_deny_when_command_not_permitted() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_policy(store)
    handler = evaluate_policy.bind(deps)

    result = await handler(
        _query(evaluated_command_name="DropDatabase"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(result, Deny)
    assert "command" in result.reason.lower()


@pytest.mark.unit
async def test_handler_returns_deny_when_conduit_does_not_match() -> None:
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_policy(store)
    handler = evaluate_policy.bind(deps)

    result = await handler(
        _query(evaluated_conduit_id=_OTHER_CONDUIT),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(result, Deny)
    assert "conduit" in result.reason.lower()


@pytest.mark.unit
async def test_handler_raises_unauthorized_when_caller_authz_denies() -> None:
    """Caller-level authz denial raises UnauthorizedError BEFORE the
    Policy is loaded — the caller isn't allowed to even ask the
    question. Distinct from a Deny result, which IS a successful query
    that returned 'no'."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store, deny=True)
    await _seed_policy(store)
    handler = evaluate_policy.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            _query(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_load_policy_when_caller_authz_denies() -> None:
    """If the caller can't ask, the handler should short-circuit before
    hitting the event store. The policy doesn't exist for this query's
    policy_id; under the no-deny path the handler would return None,
    but here it must raise UnauthorizedError instead."""
    deps = _build_deps(deny=True)  # no policy seeded
    handler = evaluate_policy.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            _query(policy_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_passes_subject_fields_through_to_evaluate() -> None:
    """Sanity check: the handler delegates query.subject_* fields to
    the pure evaluate function — not the caller's principal_id."""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_policy(store)
    handler = evaluate_policy.bind(deps)

    # Caller is _PRINCIPAL_ID (NOT in permitted set);
    # subject is _ALLOWED_PRINCIPAL (IS in permitted set).
    # Result must be Allow, proving the handler used evaluated_principal_id
    # not principal_id.
    result = await handler(
        _query(evaluated_principal_id=_ALLOWED_PRINCIPAL),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(result, Allow)


@pytest.mark.unit
def test_wire_trust_returns_handlers_bundle_with_evaluate_policy() -> None:
    deps = _build_deps()
    handlers = wire_trust(deps)
    assert isinstance(handlers, TrustHandlers)
    assert callable(handlers.evaluate_policy)
    # All 3a/3b/3c slices still wired (regression guard)
    assert callable(handlers.define_zone)
    assert callable(handlers.define_conduit)
    assert callable(handlers.define_policy)


@pytest.mark.unit
async def test_wired_handler_evaluates_through_full_composition() -> None:
    """End-to-end check that evaluate_policy survives the `with_tracing`
    wrap in wire.py. (No idempotency wrap on queries.)"""
    store = InMemoryEventStore()
    deps = _build_deps(event_store=store)
    await _seed_policy(store)
    handlers = wire_trust(deps)

    result = await handlers.evaluate_policy(
        _query(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert isinstance(result, Allow)
