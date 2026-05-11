"""Unit tests for the Capability aggregate's evolver."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.equipment.aggregates.capability import (
    Capability,
    CapabilityName,
    CapabilityStatus,
    evolve,
    fold,
)
from cora.equipment.aggregates.capability.events import (
    CapabilityDefined,
    CapabilityDeprecated,
    CapabilityVersioned,
)
from cora.equipment.features import define_capability
from cora.equipment.features.define_capability import DefineCapability

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_capability_defined_sets_status_to_defined() -> None:
    """CapabilityDefined is the genesis event; status defaults to
    Defined via the evolver. Pin so a future change (e.g. adding
    `initial_status` to the event payload) is a deliberate
    additive-state evolution."""
    capability_id = uuid4()
    state = evolve(
        None,
        CapabilityDefined(capability_id=capability_id, name="Tomography", occurred_at=_NOW),
    )
    assert state == Capability(
        id=capability_id, name=CapabilityName("Tomography"), status=CapabilityStatus.DEFINED
    )


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_capability_defined_returns_capability() -> None:
    capability_id = uuid4()
    state = fold(
        [CapabilityDefined(capability_id=capability_id, name="Tomography", occurred_at=_NOW)]
    )
    assert state == Capability(
        id=capability_id, name=CapabilityName("Tomography"), status=CapabilityStatus.DEFINED
    )


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    capability_id = uuid4()
    events = [CapabilityDefined(capability_id=capability_id, name="Tomography", occurred_at=_NOW)]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """The events the decider produces must rebuild the expected state."""
    new_id = uuid4()
    command = DefineCapability(name="  Tomography  ")  # whitespace exercises the VO trim

    events = define_capability.decide(state=None, command=command, now=_NOW, new_id=new_id)
    rebuilt = fold(events)

    assert rebuilt == Capability(
        id=new_id, name=CapabilityName("Tomography"), status=CapabilityStatus.DEFINED
    )


# ---------- CapabilityVersioned (Phase 5f-2) ----------


@pytest.mark.unit
def test_evolve_capability_defined_starts_with_null_current_version() -> None:
    """Genesis-only stream folds with current_version=None
    (additive-state pattern: pre-5f-2 streams fold cleanly without
    an upcaster)."""
    state = evolve(
        None,
        CapabilityDefined(capability_id=uuid4(), name="X", occurred_at=_NOW),
    )
    assert state.current_version is None


@pytest.mark.unit
def test_evolve_capability_versioned_flips_status_and_sets_version() -> None:
    capability_id = uuid4()
    defined = Capability(
        id=capability_id,
        name=CapabilityName("Tomography"),
        status=CapabilityStatus.DEFINED,
    )
    versioned = evolve(
        defined,
        CapabilityVersioned(capability_id=capability_id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned.status is CapabilityStatus.VERSIONED
    assert versioned.current_version == "v2"
    # Other state preserved.
    assert versioned.id == capability_id
    assert versioned.name == CapabilityName("Tomography")


@pytest.mark.unit
def test_evolve_capability_versioned_replaces_prior_version_tag() -> None:
    """Subsequent revisions overwrite current_version with the new
    label. Pinned: the latest version is what current_version reflects."""
    capability_id = uuid4()
    versioned_v1 = Capability(
        id=capability_id,
        name=CapabilityName("X"),
        status=CapabilityStatus.VERSIONED,
        current_version="v1",
    )
    versioned_v2 = evolve(
        versioned_v1,
        CapabilityVersioned(capability_id=capability_id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned_v2.current_version == "v2"


@pytest.mark.unit
def test_evolve_capability_versioned_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            CapabilityVersioned(capability_id=uuid4(), version_tag="v1", occurred_at=_NOW),
        )


# ---------- CapabilityDeprecated (Phase 5f-2) ----------


@pytest.mark.unit
def test_evolve_capability_deprecated_flips_status_and_preserves_version() -> None:
    """current_version is preserved across deprecation — the
    historical label of when the capability was last revised remains
    visible. Pinned: a future change that wiped current_version on
    deprecation would lose the audit signal."""
    capability_id = uuid4()
    versioned = Capability(
        id=capability_id,
        name=CapabilityName("X"),
        status=CapabilityStatus.VERSIONED,
        current_version="v3",
    )
    deprecated = evolve(
        versioned,
        CapabilityDeprecated(capability_id=capability_id, occurred_at=_NOW),
    )
    assert deprecated.status is CapabilityStatus.DEPRECATED
    assert deprecated.current_version == "v3"


@pytest.mark.unit
def test_evolve_capability_deprecated_from_defined_preserves_null_current_version() -> None:
    """Deprecating a Defined-only capability (never versioned) keeps
    current_version=None."""
    defined = Capability(
        id=uuid4(),
        name=CapabilityName("X"),
        status=CapabilityStatus.DEFINED,
    )
    deprecated = evolve(
        defined,
        CapabilityDeprecated(capability_id=defined.id, occurred_at=_NOW),
    )
    assert deprecated.status is CapabilityStatus.DEPRECATED
    assert deprecated.current_version is None


@pytest.mark.unit
def test_evolve_capability_deprecated_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, CapabilityDeprecated(capability_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_define_version_yields_versioned_capability() -> None:
    capability_id = uuid4()
    state = fold(
        [
            CapabilityDefined(capability_id=capability_id, name="X", occurred_at=_NOW),
            CapabilityVersioned(capability_id=capability_id, version_tag="v2", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is CapabilityStatus.VERSIONED
    assert state.current_version == "v2"


@pytest.mark.unit
def test_fold_define_version_version_yields_latest_version_tag() -> None:
    """Multi-revision fold: latest version_tag wins."""
    capability_id = uuid4()
    state = fold(
        [
            CapabilityDefined(capability_id=capability_id, name="X", occurred_at=_NOW),
            CapabilityVersioned(capability_id=capability_id, version_tag="v1", occurred_at=_NOW),
            CapabilityVersioned(capability_id=capability_id, version_tag="v2", occurred_at=_NOW),
            CapabilityVersioned(capability_id=capability_id, version_tag="v3", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.current_version == "v3"


@pytest.mark.unit
def test_fold_define_deprecate_yields_deprecated_capability() -> None:
    capability_id = uuid4()
    state = fold(
        [
            CapabilityDefined(capability_id=capability_id, name="X", occurred_at=_NOW),
            CapabilityDeprecated(capability_id=capability_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is CapabilityStatus.DEPRECATED


@pytest.mark.unit
def test_fold_define_version_deprecate_preserves_version_through_deprecation() -> None:
    """Full lifecycle audit: define → version → deprecate keeps the
    last version_tag as a historical record on the deprecated state."""
    capability_id = uuid4()
    state = fold(
        [
            CapabilityDefined(capability_id=capability_id, name="X", occurred_at=_NOW),
            CapabilityVersioned(capability_id=capability_id, version_tag="v2", occurred_at=_NOW),
            CapabilityDeprecated(capability_id=capability_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is CapabilityStatus.DEPRECATED
    assert state.current_version == "v2"
