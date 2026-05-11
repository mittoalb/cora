"""Unit tests for the `version_capability` slice's pure decider.

Multi-source-state guard: `Defined | Versioned -> Versioned`. Both
source states are valid; only Deprecated rejected. Version_tag
validated defensively in the decider.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.capability import (
    Capability,
    CapabilityCannotVersionError,
    CapabilityName,
    CapabilityNotFoundError,
    CapabilityStatus,
    CapabilityVersioned,
    InvalidCapabilityVersionTagError,
)
from cora.equipment.features import version_capability
from cora.equipment.features.version_capability import VersionCapability

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
def test_decide_emits_capability_versioned_for_each_allowed_source_status(
    source: CapabilityStatus,
) -> None:
    """Both Defined and Versioned are valid sources; the emitted
    event is identical regardless of which one preceded — no
    `from_status` on the event payload."""
    state = _capability(status=source)
    events = version_capability.decide(
        state=state,
        command=VersionCapability(capability_id=state.id, version_tag="v2"),
        now=_NOW,
    )
    assert events == [
        CapabilityVersioned(capability_id=state.id, version_tag="v2", occurred_at=_NOW)
    ]


@pytest.mark.unit
def test_decide_trims_version_tag_via_decider() -> None:
    """Defensive trim/validate in the decider so direct callers get
    the same protection as API-boundary callers."""
    state = _capability()
    events = version_capability.decide(
        state=state,
        command=VersionCapability(capability_id=state.id, version_tag="  v2  "),
        now=_NOW,
    )
    assert events[0].version_tag == "v2"


@pytest.mark.unit
def test_decide_raises_capability_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(CapabilityNotFoundError) as exc_info:
        version_capability.decide(
            state=None,
            command=VersionCapability(capability_id=target_id, version_tag="v2"),
            now=_NOW,
        )
    assert exc_info.value.capability_id == target_id


@pytest.mark.unit
def test_decide_raises_invalid_version_tag_for_empty_string() -> None:
    state = _capability()
    with pytest.raises(InvalidCapabilityVersionTagError):
        version_capability.decide(
            state=state,
            command=VersionCapability(capability_id=state.id, version_tag=""),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_version_tag_for_whitespace_only() -> None:
    state = _capability()
    with pytest.raises(InvalidCapabilityVersionTagError):
        version_capability.decide(
            state=state,
            command=VersionCapability(capability_id=state.id, version_tag="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_version_tag_for_too_long() -> None:
    state = _capability()
    with pytest.raises(InvalidCapabilityVersionTagError):
        version_capability.decide(
            state=state,
            command=VersionCapability(capability_id=state.id, version_tag="v" * 51),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_cannot_version_for_deprecated_status() -> None:
    """Deprecated is the only disallowed source state. Re-versioning
    a deprecated capability raises (would otherwise un-deprecate via
    side-effect, which is undesirable; un-deprecate would need its
    own slice if ever needed)."""
    state = _capability(status=CapabilityStatus.DEPRECATED, version="v1")
    with pytest.raises(CapabilityCannotVersionError) as exc_info:
        version_capability.decide(
            state=state,
            command=VersionCapability(capability_id=state.id, version_tag="v2"),
            now=_NOW,
        )
    assert exc_info.value.capability_id == state.id
    assert exc_info.value.current_status is CapabilityStatus.DEPRECATED


@pytest.mark.unit
def test_decide_error_message_lists_both_allowed_source_statuses() -> None:
    state = _capability(status=CapabilityStatus.DEPRECATED)
    with pytest.raises(CapabilityCannotVersionError) as exc_info:
        version_capability.decide(
            state=state,
            command=VersionCapability(capability_id=state.id, version_tag="v2"),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Deprecated" in msg
    assert "Defined" in msg
    assert "Versioned" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _capability()
    command = VersionCapability(capability_id=state.id, version_tag="v2")
    first = version_capability.decide(state=state, command=command, now=_NOW)
    second = version_capability.decide(state=state, command=command, now=_NOW)
    assert first == second


@pytest.mark.unit
def test_decide_allows_versioning_with_same_tag_for_re_attestation() -> None:
    """Deliberate divergence from strict-not-idempotent: calling
    version_capability with a tag that already matches
    state.version succeeds rather than raising. Re-attestation
    is a legitimate audit moment ("the operator confirmed v2 again on
    date X"); the multi-source Versioned → Versioned transition
    already permits the operation structurally, and tightening would
    couple the decider to history-walking (which the eventual-
    consistency stance avoids). See decider docstring for the design
    rationale."""
    state = _capability(
        status=CapabilityStatus.VERSIONED,
        version="v2",
    )
    events = version_capability.decide(
        state=state,
        command=VersionCapability(capability_id=state.id, version_tag="v2"),
        now=_NOW,
    )
    assert events == [
        CapabilityVersioned(capability_id=state.id, version_tag="v2", occurred_at=_NOW)
    ]
