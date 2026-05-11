"""Unit tests for the `version_method` slice's pure decider.

Multi-source-state guard: `Defined | Versioned -> Versioned`. Both
source states valid; only Deprecated rejected. Mirrors
`test_version_capability_decider.py` (Equipment 5f-2).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.recipe.aggregates.method import (
    InvalidMethodVersionTagError,
    Method,
    MethodCannotVersionError,
    MethodName,
    MethodNotFoundError,
    MethodStatus,
    MethodVersioned,
)
from cora.recipe.features import version_method
from cora.recipe.features.version_method import VersionMethod

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


def _method(
    *,
    status: MethodStatus = MethodStatus.DEFINED,
    current_version: str | None = None,
) -> Method:
    return Method(
        id=uuid4(),
        name=MethodName("XRF Mapping"),
        needs_capabilities=frozenset(),
        status=status,
        current_version=current_version,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [MethodStatus.DEFINED, MethodStatus.VERSIONED],
)
def test_decide_emits_method_versioned_for_each_allowed_source_status(
    source: MethodStatus,
) -> None:
    state = _method(status=source)
    events = version_method.decide(
        state=state,
        command=VersionMethod(method_id=state.id, version_tag="v2"),
        now=_NOW,
    )
    assert events == [MethodVersioned(method_id=state.id, version_tag="v2", occurred_at=_NOW)]


@pytest.mark.unit
def test_decide_trims_version_tag_via_decider() -> None:
    state = _method()
    events = version_method.decide(
        state=state,
        command=VersionMethod(method_id=state.id, version_tag="  v2  "),
        now=_NOW,
    )
    assert events[0].version_tag == "v2"


@pytest.mark.unit
def test_decide_raises_method_not_found_when_state_is_none() -> None:
    target_id = uuid4()
    with pytest.raises(MethodNotFoundError) as exc_info:
        version_method.decide(
            state=None,
            command=VersionMethod(method_id=target_id, version_tag="v2"),
            now=_NOW,
        )
    assert exc_info.value.method_id == target_id


@pytest.mark.unit
def test_decide_raises_invalid_version_tag_for_empty_string() -> None:
    state = _method()
    with pytest.raises(InvalidMethodVersionTagError):
        version_method.decide(
            state=state,
            command=VersionMethod(method_id=state.id, version_tag=""),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_version_tag_for_whitespace_only() -> None:
    state = _method()
    with pytest.raises(InvalidMethodVersionTagError):
        version_method.decide(
            state=state,
            command=VersionMethod(method_id=state.id, version_tag="   "),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_invalid_version_tag_for_too_long() -> None:
    state = _method()
    with pytest.raises(InvalidMethodVersionTagError):
        version_method.decide(
            state=state,
            command=VersionMethod(method_id=state.id, version_tag="v" * 51),
            now=_NOW,
        )


@pytest.mark.unit
def test_decide_raises_cannot_version_for_deprecated_status() -> None:
    state = _method(status=MethodStatus.DEPRECATED, current_version="v1")
    with pytest.raises(MethodCannotVersionError) as exc_info:
        version_method.decide(
            state=state,
            command=VersionMethod(method_id=state.id, version_tag="v2"),
            now=_NOW,
        )
    assert exc_info.value.method_id == state.id
    assert exc_info.value.current_status is MethodStatus.DEPRECATED


@pytest.mark.unit
def test_decide_error_message_lists_both_allowed_source_statuses() -> None:
    state = _method(status=MethodStatus.DEPRECATED)
    with pytest.raises(MethodCannotVersionError) as exc_info:
        version_method.decide(
            state=state,
            command=VersionMethod(method_id=state.id, version_tag="v2"),
            now=_NOW,
        )
    msg = str(exc_info.value)
    assert "Deprecated" in msg
    assert "Defined" in msg
    assert "Versioned" in msg


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    state = _method()
    command = VersionMethod(method_id=state.id, version_tag="v2")
    first = version_method.decide(state=state, command=command, now=_NOW)
    second = version_method.decide(state=state, command=command, now=_NOW)
    assert first == second


@pytest.mark.unit
def test_decide_allows_versioning_with_same_tag_for_re_attestation() -> None:
    """Mirrors version_capability's deliberate divergence from
    strict-not-idempotent (5f fix-pass): re-attesting the same tag
    succeeds. See decider docstring for rationale."""
    state = _method(
        status=MethodStatus.VERSIONED,
        current_version="v2",
    )
    events = version_method.decide(
        state=state,
        command=VersionMethod(method_id=state.id, version_tag="v2"),
        now=_NOW,
    )
    assert events == [MethodVersioned(method_id=state.id, version_tag="v2", occurred_at=_NOW)]
