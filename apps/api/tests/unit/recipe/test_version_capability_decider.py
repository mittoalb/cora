"""Unit tests for the `version_capability` slice's pure decider."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.family import Affordance
from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCannotVersionError,
    CapabilityCode,
    CapabilityName,
    CapabilityNotFoundError,
    CapabilityStatus,
    ExecutorShape,
    InvalidCapabilityVersionTagError,
    InvalidExecutorShapesError,
    RecipeCapabilityVersioned,
)
from cora.recipe.features.version_capability import VersionCapability, decide

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)


def _state(status: CapabilityStatus = CapabilityStatus.DEFINED) -> Capability:
    return Capability(
        id=uuid4(),
        code=CapabilityCode("cora.capability.x"),
        name=CapabilityName("X"),
        status=status,
        executor_shapes=frozenset({ExecutorShape.METHOD}),
    )


def _cmd(state: Capability, **overrides: object) -> VersionCapability:
    base: dict[str, object] = dict(
        capability_id=state.id,
        version_tag="v2",
        required_affordances=frozenset({Affordance.ROTATABLE}),
        executor_shapes=frozenset({ExecutorShape.METHOD}),
    )
    base.update(overrides)
    return VersionCapability(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_decide_versions_from_defined() -> None:
    state = _state(CapabilityStatus.DEFINED)
    events = decide(state=state, command=_cmd(state), now=_NOW)
    assert len(events) == 1
    assert isinstance(events[0], RecipeCapabilityVersioned)
    assert events[0].version_tag == "v2"


@pytest.mark.unit
def test_decide_versions_from_versioned() -> None:
    """Multi-source: subsequent revisions allowed."""
    state = _state(CapabilityStatus.VERSIONED)
    events = decide(state=state, command=_cmd(state, version_tag="v3"), now=_NOW)
    assert events[0].version_tag == "v3"


@pytest.mark.unit
def test_decide_raises_not_found_when_state_is_none() -> None:
    cmd = VersionCapability(
        capability_id=uuid4(),
        version_tag="v2",
        required_affordances=frozenset[Affordance](),
        executor_shapes=frozenset({ExecutorShape.METHOD}),
    )
    with pytest.raises(CapabilityNotFoundError):
        decide(state=None, command=cmd, now=_NOW)


@pytest.mark.unit
def test_decide_raises_cannot_version_when_deprecated() -> None:
    state = _state(CapabilityStatus.DEPRECATED)
    with pytest.raises(CapabilityCannotVersionError) as exc:
        decide(state=state, command=_cmd(state), now=_NOW)
    assert exc.value.current_status == CapabilityStatus.DEPRECATED


@pytest.mark.unit
def test_decide_raises_on_whitespace_only_version_tag() -> None:
    state = _state()
    with pytest.raises(InvalidCapabilityVersionTagError):
        decide(state=state, command=_cmd(state, version_tag="   "), now=_NOW)


@pytest.mark.unit
def test_decide_raises_on_empty_executor_shapes() -> None:
    state = _state()
    with pytest.raises(InvalidExecutorShapesError):
        decide(
            state=state,
            command=_cmd(state, executor_shapes=frozenset[ExecutorShape]()),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_replaces_required_affordances_wholesale() -> None:
    state = _state()
    events = decide(
        state=state,
        command=_cmd(
            state,
            required_affordances=frozenset({Affordance.IMAGEABLE, Affordance.TRIGGERABLE}),
        ),
        now=_NOW,
    )
    assert events[0].required_affordances == frozenset(
        {Affordance.IMAGEABLE, Affordance.TRIGGERABLE}
    )


@pytest.mark.unit
def test_decide_re_attestation_allows_same_tag() -> None:
    """Re-attestation: calling version_capability with the same tag is valid."""
    state = _state(CapabilityStatus.VERSIONED)
    events1 = decide(state=state, command=_cmd(state, version_tag="v2"), now=_NOW)
    events2 = decide(state=state, command=_cmd(state, version_tag="v2"), now=_NOW)
    assert events1 == events2
    assert len(events1) == 1
