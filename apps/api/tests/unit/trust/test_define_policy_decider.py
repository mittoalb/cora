"""Unit tests for the `define_policy` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.trust.aggregates.policy import (
    InvalidPolicyNameError,
    Policy,
    PolicyAlreadyExistsError,
    PolicyDefined,
    PolicyName,
)
from cora.trust.features import define_policy
from cora.trust.features.define_policy import DefinePolicy

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_decide_emits_policy_defined_when_stream_is_empty() -> None:
    new_id = uuid4()
    conduit_id = uuid4()
    p1 = uuid4()
    events = define_policy.decide(
        state=None,
        command=DefinePolicy(
            name="Beam-team",
            conduit_id=conduit_id,
            principals_permitted=frozenset({p1}),
            commands_permitted=frozenset({"RegisterActor"}),
        ),
        now=_NOW,
        new_id=new_id,
    )
    assert len(events) == 1
    e = events[0]
    assert isinstance(e, PolicyDefined)
    assert e.policy_id == new_id
    assert e.name == "Beam-team"
    assert e.conduit_id == conduit_id
    assert set(e.principals_permitted) == {p1}
    assert set(e.commands_permitted) == {"RegisterActor"}
    assert e.occurred_at == _NOW


@pytest.mark.unit
def test_decide_trims_name_via_value_object() -> None:
    events = define_policy.decide(
        state=None,
        command=DefinePolicy(
            name="  Beam-team  ",
            conduit_id=uuid4(),
            principals_permitted=frozenset({uuid4()}),
            commands_permitted=frozenset({"RegisterActor"}),
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].name == "Beam-team"


@pytest.mark.unit
def test_decide_rejects_invalid_name() -> None:
    with pytest.raises(InvalidPolicyNameError):
        define_policy.decide(
            state=None,
            command=DefinePolicy(
                name="",
                conduit_id=uuid4(),
                principals_permitted=frozenset({uuid4()}),
                commands_permitted=frozenset({"RegisterActor"}),
            ),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decide_rejects_existing_state() -> None:
    existing = Policy(
        id=uuid4(),
        name=PolicyName("Existing"),
        conduit_id=uuid4(),
        principals_permitted=frozenset({uuid4()}),
        commands_permitted=frozenset({"RegisterActor"}),
    )
    with pytest.raises(PolicyAlreadyExistsError) as exc_info:
        define_policy.decide(
            state=existing,
            command=DefinePolicy(
                name="Other",
                conduit_id=uuid4(),
                principals_permitted=frozenset(),
                commands_permitted=frozenset(),
            ),
            now=_NOW,
            new_id=uuid4(),
        )
    assert exc_info.value.policy_id == existing.id


@pytest.mark.unit
def test_decide_allows_empty_permission_sets() -> None:
    """Deny-all policies (empty allow lists) are valid by construction —
    see Policy aggregate's state.py docstring. Pin so a future
    "must have at least one principal" rule has to flip this."""
    events = define_policy.decide(
        state=None,
        command=DefinePolicy(
            name="Locked",
            conduit_id=uuid4(),
            principals_permitted=frozenset(),
            commands_permitted=frozenset(),
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].principals_permitted == []
    assert events[0].commands_permitted == []


@pytest.mark.unit
def test_decide_does_not_validate_conduit_existence() -> None:
    """Eventual-consistency stance (same as Conduit→Zone in 3b): the
    decider does NOT verify that `conduit_id` references an existing
    Conduit. Pinned so a future "validate at command time" refactor
    has to flip this."""
    events = define_policy.decide(
        state=None,
        command=DefinePolicy(
            name="Dangling",
            conduit_id=uuid4(),  # random — no corresponding Conduit events
            principals_permitted=frozenset({uuid4()}),
            commands_permitted=frozenset({"X"}),
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    new_id = uuid4()
    conduit = uuid4()
    p1 = uuid4()
    command = DefinePolicy(
        name="Beam-team",
        conduit_id=conduit,
        principals_permitted=frozenset({p1}),
        commands_permitted=frozenset({"RegisterActor"}),
    )
    first = define_policy.decide(state=None, command=command, now=_NOW, new_id=new_id)
    second = define_policy.decide(state=None, command=command, now=_NOW, new_id=new_id)
    assert first == second
