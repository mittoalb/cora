"""Unit tests for Method.supplies_needed (Phase 10b).

Covers:
  - State default + frozenset shape
  - Decider per-element validation (whitespace-only, oversized, trims)
  - Decider accepts empty + populated
  - Event payload sorted lexically (deterministic hash)
  - Event roundtrip preserves supplies_needed
  - Pre-10b event payload (no supplies_needed key) folds via additive
    evolution to empty frozenset (forward-compat critical pin)
  - Evolver fold for MethodDefined sets the field
  - Each transition (Versioned, Deprecated, ParametersSchemaUpdated)
    PRESERVES supplies_needed through (preserve-fields invariant)

Asymmetric-with-capabilities_needed design (str vs UUID) is exercised
implicitly throughout — supplies_needed elements are kind STRINGS,
never instance UUIDs.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.event_store import StoredEvent
from cora.recipe.aggregates.method import (
    InvalidMethodSuppliesNeededError,
    Method,
    MethodDefined,
    MethodDeprecated,
    MethodName,
    MethodParametersSchemaUpdated,
    MethodStatus,
    MethodVersioned,
    event_type_name,
    evolve,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.features import define_method
from cora.recipe.features.define_method import DefineMethod

_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=UTC)


# ---------- Method state shape ----------


@pytest.mark.unit
def test_method_state_defaults_supplies_needed_to_empty_frozenset() -> None:
    """Pre-10b Methods (no payload key) and freshly-defined Methods
    that don't declare supplies both land at empty. The default-factory
    keeps state shape uniform."""
    method = Method(
        id=uuid4(),
        name=MethodName("X"),
    )
    assert method.supplies_needed == frozenset()


@pytest.mark.unit
def test_method_state_carries_supplied_supplies_needed() -> None:
    method = Method(
        id=uuid4(),
        name=MethodName("Tomography"),
        supplies_needed=frozenset({"PhotonBeam", "LiquidNitrogen"}),
    )
    assert method.supplies_needed == frozenset({"PhotonBeam", "LiquidNitrogen"})


# ---------- Decider validation ----------


@pytest.mark.unit
def test_decider_accepts_empty_supplies_needed() -> None:
    """Sample-cleaning Method valid: no Capability AND no Supply
    requirement (purely procedural)."""
    events = define_method.decide(
        state=None,
        command=DefineMethod(
            name="Sample Cleaning",
            capabilities_needed=frozenset(),
            supplies_needed=frozenset(),
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert events[0].supplies_needed == []


@pytest.mark.unit
def test_decider_accepts_populated_supplies_needed() -> None:
    events = define_method.decide(
        state=None,
        command=DefineMethod(
            name="Tomography",
            capabilities_needed=frozenset(),
            supplies_needed=frozenset({"PhotonBeam", "LiquidNitrogen"}),
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert set(events[0].supplies_needed) == {"PhotonBeam", "LiquidNitrogen"}


@pytest.mark.unit
def test_decider_trims_each_kind_string() -> None:
    """Each kind goes through validate_bounded_text (1-50 chars,
    trimmed). Mirrors Method's own MethodName trim behavior."""
    events = define_method.decide(
        state=None,
        command=DefineMethod(
            name="X",
            capabilities_needed=frozenset(),
            supplies_needed=frozenset({"  PhotonBeam  ", "LiquidNitrogen"}),
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert "PhotonBeam" in set(events[0].supplies_needed)
    assert "  PhotonBeam  " not in set(events[0].supplies_needed)


@pytest.mark.unit
def test_decider_rejects_whitespace_only_kind() -> None:
    with pytest.raises(InvalidMethodSuppliesNeededError):
        define_method.decide(
            state=None,
            command=DefineMethod(
                name="X",
                capabilities_needed=frozenset(),
                supplies_needed=frozenset({"   "}),
            ),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decider_rejects_empty_kind() -> None:
    with pytest.raises(InvalidMethodSuppliesNeededError):
        define_method.decide(
            state=None,
            command=DefineMethod(
                name="X",
                capabilities_needed=frozenset(),
                supplies_needed=frozenset({""}),
            ),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decider_rejects_oversized_kind() -> None:
    """Per-element bound is 50 chars (mirrors Supply.kind shape)."""
    with pytest.raises(InvalidMethodSuppliesNeededError):
        define_method.decide(
            state=None,
            command=DefineMethod(
                name="X",
                capabilities_needed=frozenset(),
                supplies_needed=frozenset({"x" * 51}),
            ),
            now=_NOW,
            new_id=uuid4(),
        )


@pytest.mark.unit
def test_decider_accepts_max_length_kind() -> None:
    boundary = "x" * 50
    events = define_method.decide(
        state=None,
        command=DefineMethod(
            name="X",
            capabilities_needed=frozenset(),
            supplies_needed=frozenset({boundary}),
        ),
        now=_NOW,
        new_id=uuid4(),
    )
    assert boundary in set(events[0].supplies_needed)


# ---------- Event payload determinism ----------


@pytest.mark.unit
def test_to_payload_sorts_supplies_needed_lexically() -> None:
    """Same logical kind set must serialize to the same payload bytes
    (idempotency-hash determinism). Sorting in to_payload is the
    contract."""
    event = MethodDefined(
        method_id=uuid4(),
        name="X",
        capabilities_needed=[],
        supplies_needed=["LiquidNitrogen", "PhotonBeam", "ComputePool"],
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    assert payload["supplies_needed"] == ["ComputePool", "LiquidNitrogen", "PhotonBeam"]


@pytest.mark.unit
def test_event_round_trips_with_supplies_needed() -> None:
    original = MethodDefined(
        method_id=uuid4(),
        name="Tomography",
        capabilities_needed=[],
        supplies_needed=["LiquidNitrogen", "PhotonBeam"],
        occurred_at=_NOW,
    )
    stored = _stored("MethodDefined", to_payload(original))
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, MethodDefined)
    # Sets equal (payload sorts; from_stored preserves payload order).
    assert set(rebuilt.supplies_needed) == {"LiquidNitrogen", "PhotonBeam"}


# ---------- Pre-10b backward-compat (additive evolution) ----------


@pytest.mark.unit
def test_pre_10b_event_payload_folds_with_empty_supplies_needed() -> None:
    """Critical forward-compat pin. Pre-10b MethodDefined payloads
    have NO supplies_needed key. additive-evolution: from_stored uses
    payload.get(..., default), so the rebuilt event carries empty
    list, and the evolver folds into empty frozenset."""
    pre_10b_payload: dict[str, object] = {
        "method_id": str(uuid4()),
        "name": "Pre-10b Method",
        "capabilities_needed": [],
        "occurred_at": _NOW.isoformat(),
        # No supplies_needed key — pre-10b payload shape.
    }
    stored = _stored("MethodDefined", pre_10b_payload)
    rebuilt = from_stored(stored)
    assert isinstance(rebuilt, MethodDefined)
    assert rebuilt.supplies_needed == []
    state = evolve(None, rebuilt)
    assert state.supplies_needed == frozenset()


# ---------- Evolver fold ----------


@pytest.mark.unit
def test_evolve_method_defined_sets_supplies_needed() -> None:
    method_id = uuid4()
    event = MethodDefined(
        method_id=method_id,
        name="Tomography",
        capabilities_needed=[],
        supplies_needed=["PhotonBeam", "LiquidNitrogen"],
        occurred_at=_NOW,
    )
    state = evolve(None, event)
    assert state.supplies_needed == frozenset({"PhotonBeam", "LiquidNitrogen"})


# ---------- Preserve-fields invariant per transition ----------


def _seed_state(supplies: frozenset[str]) -> Method:
    return evolve(
        None,
        MethodDefined(
            method_id=uuid4(),
            name="Tomography",
            capabilities_needed=[],
            supplies_needed=list(supplies),
            occurred_at=_NOW,
        ),
    )


@pytest.mark.unit
def test_evolve_method_versioned_preserves_supplies_needed() -> None:
    seed = _seed_state(frozenset({"PhotonBeam"}))
    after = evolve(seed, MethodVersioned(method_id=seed.id, version_tag="v2", occurred_at=_NOW))
    assert after.supplies_needed == frozenset({"PhotonBeam"})
    assert after.status is MethodStatus.VERSIONED


@pytest.mark.unit
def test_evolve_method_deprecated_preserves_supplies_needed() -> None:
    seed = _seed_state(frozenset({"PhotonBeam", "LiquidNitrogen"}))
    after = evolve(seed, MethodDeprecated(method_id=seed.id, occurred_at=_NOW))
    assert after.supplies_needed == frozenset({"PhotonBeam", "LiquidNitrogen"})
    assert after.status is MethodStatus.DEPRECATED


@pytest.mark.unit
def test_evolve_method_parameters_schema_updated_preserves_supplies_needed() -> None:
    """Orthogonal-facet update must NOT wipe supplies_needed."""
    seed = _seed_state(frozenset({"PhotonBeam"}))
    after = evolve(
        seed,
        MethodParametersSchemaUpdated(
            method_id=seed.id,
            parameters_schema={"type": "object"},
            occurred_at=_NOW,
        ),
    )
    assert after.supplies_needed == frozenset({"PhotonBeam"})


@pytest.mark.unit
def test_fold_full_lifecycle_preserves_supplies_needed() -> None:
    """End-to-end: defined → versioned → schema-updated → deprecated.
    supplies_needed survives the whole chain."""
    method_id = uuid4()
    state = fold(
        [
            MethodDefined(
                method_id=method_id,
                name="Tomography",
                capabilities_needed=[],
                supplies_needed=["PhotonBeam", "LiquidNitrogen"],
                occurred_at=_NOW,
            ),
            MethodVersioned(method_id=method_id, version_tag="v2", occurred_at=_NOW),
            MethodParametersSchemaUpdated(
                method_id=method_id,
                parameters_schema={"type": "object"},
                occurred_at=_NOW,
            ),
            MethodDeprecated(method_id=method_id, occurred_at=_NOW),
        ]
    )
    assert state is not None
    assert state.supplies_needed == frozenset({"PhotonBeam", "LiquidNitrogen"})
    assert state.status is MethodStatus.DEPRECATED


# ---------- Helper ----------


def _stored(event_type: str, payload: dict[str, object]) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Method",
        stream_id=uuid4(),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


# ---------- event_type_name (sanity) ----------


@pytest.mark.unit
def test_event_type_name_for_method_defined_unchanged() -> None:
    """The event class name doesn't change in 10b — additive payload
    evolution only. Pinned because subscribers route by event_type."""
    event = MethodDefined(
        method_id=uuid4(),
        name="X",
        capabilities_needed=[],
        supplies_needed=[],
        occurred_at=_NOW,
    )
    assert event_type_name(event) == "MethodDefined"


# Suppress pyright warnings on the test-only state seed factory.
_ = UUID  # marker so the import is referenced (used by stored helper return type).
