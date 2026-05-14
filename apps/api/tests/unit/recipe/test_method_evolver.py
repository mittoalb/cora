"""Unit tests for the Method aggregate's evolver.

Pinned: list[UUID] in event payload converts to frozenset[UUID] in
state (set semantics for Plan-binding superset checks).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.recipe.aggregates.method import (
    Method,
    MethodName,
    MethodStatus,
    evolve,
    fold,
)
from cora.recipe.aggregates.method.events import (
    MethodDefined,
    MethodDeprecated,
    MethodParametersSchemaUpdated,
    MethodVersioned,
)
from cora.recipe.features import define_method
from cora.recipe.features.define_method import DefineMethod

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)


@pytest.mark.unit
def test_evolve_method_defined_sets_status_to_defined() -> None:
    """MethodDefined is the genesis event; status defaults to Defined
    via the evolver. Pin so a future change (e.g. adding
    `initial_status` to the event payload) is a deliberate
    additive-state evolution."""
    method_id = uuid4()
    cap1 = uuid4()
    state = evolve(
        None,
        MethodDefined(
            method_id=method_id,
            name="XRF Fly Mapping",
            needs_capabilities=[cap1],
            occurred_at=_NOW,
        ),
    )
    assert state == Method(
        id=method_id,
        name=MethodName("XRF Fly Mapping"),
        needs_capabilities=frozenset({cap1}),
        status=MethodStatus.DEFINED,
    )


@pytest.mark.unit
def test_evolve_converts_list_to_frozenset() -> None:
    """Event payload carries `list[UUID]` (JSON-friendly); state
    holds `frozenset[UUID]` (set semantics for Plan-binding
    superset checks). Locked because a future refactor that
    drops the conversion would silently break Plan-time set
    operations."""
    cap1 = uuid4()
    cap2 = uuid4()
    cap3 = uuid4()
    state = evolve(
        None,
        MethodDefined(
            method_id=uuid4(),
            name="X",
            needs_capabilities=[cap1, cap2, cap3, cap1],  # duplicate
            occurred_at=_NOW,
        ),
    )
    assert state.needs_capabilities == frozenset({cap1, cap2, cap3})
    assert isinstance(state.needs_capabilities, frozenset)


@pytest.mark.unit
def test_evolve_handles_empty_needs_capabilities() -> None:
    """Procedural Methods (no equipment requirement) fold to empty
    frozenset; Plan-binding's superset check still works
    (frozenset() ⊆ anything)."""
    state = evolve(
        None,
        MethodDefined(
            method_id=uuid4(),
            name="Sample Cleaning",
            needs_capabilities=[],
            occurred_at=_NOW,
        ),
    )
    assert state.needs_capabilities == frozenset()


@pytest.mark.unit
def test_fold_empty_event_list_returns_none() -> None:
    assert fold([]) is None


@pytest.mark.unit
def test_fold_single_method_defined_returns_method() -> None:
    method_id = uuid4()
    cap1 = uuid4()
    state = fold(
        [
            MethodDefined(
                method_id=method_id,
                name="Step Tomography",
                needs_capabilities=[cap1],
                occurred_at=_NOW,
            )
        ]
    )
    assert state == Method(
        id=method_id,
        name=MethodName("Step Tomography"),
        needs_capabilities=frozenset({cap1}),
        status=MethodStatus.DEFINED,
    )


@pytest.mark.unit
def test_fold_is_pure_same_input_same_output() -> None:
    cap1 = uuid4()
    events = [
        MethodDefined(
            method_id=uuid4(),
            name="X",
            needs_capabilities=[cap1],
            occurred_at=_NOW,
        )
    ]
    assert fold(events) == fold(events)


@pytest.mark.unit
def test_decider_and_evolver_round_trip() -> None:
    """End-to-end: decider produces events that the evolver folds back
    to the expected state."""
    new_id = uuid4()
    cap1 = UUID("01900000-0000-7000-8000-000000000111")
    cap2 = UUID("01900000-0000-7000-8000-000000000222")
    command = DefineMethod(
        name="  XRF Fly Mapping  ",
        needs_capabilities=frozenset({cap1, cap2}),
    )
    events = define_method.decide(state=None, command=command, now=_NOW, new_id=new_id)
    rebuilt = fold(events)
    assert rebuilt == Method(
        id=new_id,
        name=MethodName("XRF Fly Mapping"),
        needs_capabilities=frozenset({cap1, cap2}),
        status=MethodStatus.DEFINED,
    )


# ---------- MethodVersioned (Phase 6b) ----------


@pytest.mark.unit
def test_evolve_method_defined_starts_with_null_version() -> None:
    """Genesis-only stream folds with version=None
    (additive-state pattern; pre-6b streams fold cleanly without
    an upcaster)."""
    state = evolve(
        None,
        MethodDefined(method_id=uuid4(), name="X", needs_capabilities=[], occurred_at=_NOW),
    )
    assert state.version is None


@pytest.mark.unit
def test_evolve_method_versioned_flips_status_and_sets_version() -> None:
    method_id = uuid4()
    cap1 = uuid4()
    defined = Method(
        id=method_id,
        name=MethodName("XRF Mapping"),
        needs_capabilities=frozenset({cap1}),
        status=MethodStatus.DEFINED,
    )
    versioned = evolve(
        defined,
        MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned.status is MethodStatus.VERSIONED
    assert versioned.version == "v2"
    # needs_capabilities preserved.
    assert versioned.needs_capabilities == frozenset({cap1})
    assert versioned.id == method_id


@pytest.mark.unit
def test_evolve_method_versioned_replaces_prior_version_tag() -> None:
    """Subsequent revisions overwrite version with the new label."""
    method_id = uuid4()
    versioned_v1 = Method(
        id=method_id,
        name=MethodName("X"),
        needs_capabilities=frozenset(),
        status=MethodStatus.VERSIONED,
        version="v1",
    )
    versioned_v2 = evolve(
        versioned_v1,
        MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned_v2.version == "v2"


@pytest.mark.unit
def test_evolve_method_versioned_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            MethodVersioned(method_id=uuid4(), version_tag="v1", occurred_at=_NOW),
        )


# ---------- MethodDeprecated (Phase 6b) ----------


@pytest.mark.unit
def test_evolve_method_deprecated_flips_status_and_preserves_version() -> None:
    """version is preserved across deprecation. Mirrors
    Capability's preserve-on-deprecate semantics from Equipment 5f-2."""
    method_id = uuid4()
    cap1 = uuid4()
    versioned = Method(
        id=method_id,
        name=MethodName("X"),
        needs_capabilities=frozenset({cap1}),
        status=MethodStatus.VERSIONED,
        version="v3",
    )
    deprecated = evolve(
        versioned,
        MethodDeprecated(method_id=method_id, occurred_at=_NOW),
    )
    assert deprecated.status is MethodStatus.DEPRECATED
    assert deprecated.version == "v3"
    # needs_capabilities preserved across deprecation too.
    assert deprecated.needs_capabilities == frozenset({cap1})


@pytest.mark.unit
def test_evolve_method_deprecated_from_defined_preserves_null_version() -> None:
    defined = Method(
        id=uuid4(),
        name=MethodName("X"),
        needs_capabilities=frozenset(),
        status=MethodStatus.DEFINED,
    )
    deprecated = evolve(
        defined,
        MethodDeprecated(method_id=defined.id, occurred_at=_NOW),
    )
    assert deprecated.status is MethodStatus.DEPRECATED
    assert deprecated.version is None


@pytest.mark.unit
def test_evolve_method_deprecated_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(None, MethodDeprecated(method_id=uuid4(), occurred_at=_NOW))


@pytest.mark.unit
def test_fold_define_version_yields_versioned_method() -> None:
    method_id = uuid4()
    state = fold(
        [
            MethodDefined(method_id=method_id, name="X", needs_capabilities=[], occurred_at=_NOW),
            MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is MethodStatus.VERSIONED
    assert state.version == "v2"


@pytest.mark.unit
def test_fold_define_version_version_yields_latest_version_tag() -> None:
    """Multi-revision fold: latest version_tag wins."""
    method_id = uuid4()
    state = fold(
        [
            MethodDefined(method_id=method_id, name="X", needs_capabilities=[], occurred_at=_NOW),
            MethodVersioned(method_id=method_id, version_tag="v1", occurred_at=_NOW),
            MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW),
            MethodVersioned(method_id=method_id, version_tag="v3", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.version == "v3"


@pytest.mark.unit
def test_fold_define_deprecate_yields_deprecated_method() -> None:
    method_id = uuid4()
    state = fold(
        [
            MethodDefined(method_id=method_id, name="X", needs_capabilities=[], occurred_at=_NOW),
            MethodDeprecated(method_id=method_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is MethodStatus.DEPRECATED


@pytest.mark.unit
def test_fold_define_version_deprecate_preserves_version_through_deprecation() -> None:
    """Full lifecycle audit: define → version → deprecate keeps the
    last version_tag as a historical record on the deprecated state."""
    method_id = uuid4()
    state = fold(
        [
            MethodDefined(method_id=method_id, name="X", needs_capabilities=[], occurred_at=_NOW),
            MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW),
            MethodDeprecated(method_id=method_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.status is MethodStatus.DEPRECATED
    assert state.version == "v2"


@pytest.mark.unit
def test_evolve_method_versioned_preserves_needs_capabilities() -> None:
    """Critical pin: needs_capabilities MUST carry through the
    version transition. Same safety-net pattern as
    test_evolve_<X>_preserves_capabilities for Asset (5f-1)."""
    cap1 = uuid4()
    cap2 = uuid4()
    defined = Method(
        id=uuid4(),
        name=MethodName("X"),
        needs_capabilities=frozenset({cap1, cap2}),
        status=MethodStatus.DEFINED,
    )
    versioned = evolve(
        defined,
        MethodVersioned(method_id=defined.id, version_tag="v2", occurred_at=_NOW),
    )
    assert versioned.needs_capabilities == frozenset({cap1, cap2})


# ---------- MethodParametersSchemaUpdated (Phase 6g-a) ----------


_SCHEMA_A = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {"energy_kev": {"type": "number"}},
}


@pytest.mark.unit
def test_evolve_method_defined_starts_with_null_parameters_schema() -> None:
    """Genesis-only stream folds with parameters_schema=None
    (additive-state pattern; pre-6g-a streams fold cleanly without
    an upcaster)."""
    state = evolve(
        None,
        MethodDefined(method_id=uuid4(), name="X", needs_capabilities=[], occurred_at=_NOW),
    )
    assert state.parameters_schema is None


@pytest.mark.unit
def test_evolve_method_parameters_schema_updated_sets_schema_and_preserves_status() -> None:
    """Schema update is orthogonal to lifecycle: status preserved on apply."""
    method_id = uuid4()
    cap1 = uuid4()
    defined = Method(
        id=method_id,
        name=MethodName("X"),
        needs_capabilities=frozenset({cap1}),
        status=MethodStatus.DEFINED,
    )
    updated = evolve(
        defined,
        MethodParametersSchemaUpdated(
            method_id=method_id, parameters_schema=_SCHEMA_A, occurred_at=_NOW
        ),
    )
    assert updated.parameters_schema == _SCHEMA_A
    assert updated.status is MethodStatus.DEFINED
    assert updated.needs_capabilities == frozenset({cap1})


@pytest.mark.unit
def test_evolve_method_parameters_schema_updated_with_none_clears_schema() -> None:
    method_id = uuid4()
    state_with_schema = Method(
        id=method_id,
        name=MethodName("X"),
        needs_capabilities=frozenset(),
        status=MethodStatus.DEFINED,
        parameters_schema=_SCHEMA_A,
    )
    cleared = evolve(
        state_with_schema,
        MethodParametersSchemaUpdated(
            method_id=method_id, parameters_schema=None, occurred_at=_NOW
        ),
    )
    assert cleared.parameters_schema is None


@pytest.mark.unit
def test_evolve_method_parameters_schema_updated_on_empty_state_raises() -> None:
    with pytest.raises(ValueError, match="cannot be applied to empty state"):
        evolve(
            None,
            MethodParametersSchemaUpdated(
                method_id=uuid4(), parameters_schema=_SCHEMA_A, occurred_at=_NOW
            ),
        )


@pytest.mark.unit
def test_evolve_method_versioned_preserves_parameters_schema() -> None:
    """Critical pin: parameters_schema MUST carry through the version
    transition. Mirrors `test_evolve_method_versioned_preserves_needs_capabilities`."""
    state = Method(
        id=uuid4(),
        name=MethodName("X"),
        needs_capabilities=frozenset(),
        status=MethodStatus.DEFINED,
        parameters_schema=_SCHEMA_A,
    )
    versioned = evolve(
        state, MethodVersioned(method_id=state.id, version_tag="v2", occurred_at=_NOW)
    )
    assert versioned.parameters_schema == _SCHEMA_A


@pytest.mark.unit
def test_evolve_method_deprecated_preserves_parameters_schema() -> None:
    """Critical pin: parameters_schema MUST carry through the deprecate
    transition (audit-relevant historical artifact)."""
    state = Method(
        id=uuid4(),
        name=MethodName("X"),
        needs_capabilities=frozenset(),
        status=MethodStatus.VERSIONED,
        version="v1",
        parameters_schema=_SCHEMA_A,
    )
    deprecated = evolve(state, MethodDeprecated(method_id=state.id, occurred_at=_NOW))
    assert deprecated.parameters_schema == _SCHEMA_A


@pytest.mark.unit
def test_fold_define_update_schema_yields_state_with_schema() -> None:
    method_id = uuid4()
    state = fold(
        [
            MethodDefined(method_id=method_id, name="X", needs_capabilities=[], occurred_at=_NOW),
            MethodParametersSchemaUpdated(
                method_id=method_id, parameters_schema=_SCHEMA_A, occurred_at=_NOW
            ),
        ]
    )
    assert state is not None
    assert state.parameters_schema == _SCHEMA_A
    assert state.status is MethodStatus.DEFINED


@pytest.mark.unit
def test_fold_define_update_schema_version_carries_schema_through_versioning() -> None:
    """Multi-event fold: schema set first, then versioning preserves it."""
    method_id = uuid4()
    state = fold(
        [
            MethodDefined(method_id=method_id, name="X", needs_capabilities=[], occurred_at=_NOW),
            MethodParametersSchemaUpdated(
                method_id=method_id, parameters_schema=_SCHEMA_A, occurred_at=_NOW
            ),
            MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.parameters_schema == _SCHEMA_A
    assert state.version == "v2"
    assert state.status is MethodStatus.VERSIONED
