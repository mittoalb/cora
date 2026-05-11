"""Unit tests for the `deprecate_capability` slice's pure decider.

Multi-source-state guard: `Defined | Versioned -> Deprecated`. Same
source-set as version_capability but the target is terminal.
Re-deprecating raises (strict-not-idempotent).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.capability import (
    Capability,
    CapabilityCannotDeprecateError,
    CapabilityDeprecated,
    CapabilityName,
    CapabilityNotFoundError,
    CapabilityStatus,
)
from cora.equipment.features import deprecate_capability
from cora.equipment.features.deprecate_capability import DeprecateCapability

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _capability(
    *,
    status: CapabilityStatus = CapabilityStatus.DEFINED,
    version: str | None = None,
) -> Capability:
    return Capability(
        id=uuid4(),
        name=CapabilityName("Tomography"),
        status=status,
        version=version,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [CapabilityStatus.DEFINED, CapabilityStatus.VERSIONED],
)
def test_decide_emits_capability_deprecated_for_each_allowed_source_status(
    source: CapabilityStatus,
) -> None:
    state = _capability(status=source)
    events = deprecate_capability.decide(
        state=state,
        command=DeprecateCapability(capability_id=state.id),
        now=_NOW,
    )
    assert events == [CapabilityDeprecated(capability_id=state.id, occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_raises_capability_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(CapabilityNotFoundError) as exc_info:
        deprecate_capability.decide(
            state=None,
            command=DeprecateCapability(capability_id=target_id),
            now=_NOW,
        )
    assert exc_info.value.capability_id == target_id


@pytest.mark.unit
def test_decide_raises_cannot_deprecate_when_already_deprecated() -> None:
    """Strict-not-idempotent: re-deprecating raises."""
    state = _capability(status=CapabilityStatus.DEPRECATED)
    with pytest.raises(CapabilityCannotDeprecateError) as exc_info:
        deprecate_capability.decide(
            state=state,
            command=DeprecateCapability(capability_id=state.id),
            now=_NOW,
        )
    assert exc_info.value.capability_id == state.id
    assert exc_info.value.current_status is CapabilityStatus.DEPRECATED


@pytest.mark.unit
def test_decide_error_message_lists_both_allowed_source_statuses() -> None:
    state = _capability(status=CapabilityStatus.DEPRECATED)
    with pytest.raises(CapabilityCannotDeprecateError) as exc_info:
        deprecate_capability.decide(
            state=state,
            command=DeprecateCapability(capability_id=state.id),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Defined" in msg
    assert "Versioned" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _capability()
    command = DeprecateCapability(capability_id=state.id)
    first = deprecate_capability.decide(state=state, command=command, now=_NOW)
    second = deprecate_capability.decide(state=state, command=command, now=_NOW)
    assert first == second
