"""Unit tests for the parameters-schema subset guard.

Pinned: `update_method_parameters_schema` decider enforces
`Method.parameters_schema ⊆ Capability.parameter_schema` when the Method has a
`capability_id` and the bound Capability has a `parameter_schema`. One-sided
cases (Method has no schema, or Capability has no schema, or Method has no
capability_id) skip the check.

Mirrors the shape of `test_define_plan_decider.py`'s affordance-cover unit
tests (decider invocation directly with a Capability fixture, no PG).
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from cora.recipe.aggregates.capability import (
    Capability,
    CapabilityCode,
    CapabilityName,
    ExecutorShape,
)
from cora.recipe.aggregates.method import (
    Method,
    MethodName,
    MethodParametersNotSubsetError,
    MethodStatus,
)
from cora.recipe.features.update_method_parameters_schema import (
    UpdateMethodParametersSchema,
)
from cora.recipe.features.update_method_parameters_schema.decider import decide

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _method(
    *,
    capability_id: object | None = None,
    parameters_schema: dict[str, Any] | None = None,
) -> Method:
    """Build a Method fixture for the subset-guard tests."""
    return Method(
        id=uuid4(),
        name=MethodName("XRF Mapping"),
        needed_families=frozenset(),
        status=MethodStatus.DEFINED,
        parameters_schema=parameters_schema,
        capability_id=capability_id,  # type: ignore[arg-type]
    )


def _capability(parameter_schema: dict[str, Any] | None = None) -> Capability:
    """Build a Capability fixture, optionally with a parameter_schema."""
    return Capability(
        id=uuid4(),
        code=CapabilityCode("cora.capability.x"),
        name=CapabilityName("X"),
        executor_shapes=frozenset({ExecutorShape.METHOD}),
        parameter_schema=parameter_schema,
    )


_BROAD_CAPABILITY_SCHEMA: dict[str, Any] = {
    "$schema": _DRAFT,
    "type": "object",
    "properties": {
        "energy": {"type": "number", "minimum": 5, "maximum": 50},
        "filter_material": {"type": "string", "enum": ["Cu", "Al", "Mo"]},
        "exposure_ms": {"type": "integer", "minimum": 1, "maximum": 1000},
    },
    "required": ["energy"],
}


@pytest.mark.unit
def test_decide_passes_when_method_schema_is_strict_subset_of_capability() -> None:
    """Happy path: Method schema narrows Capability's contract (smaller
    enum + narrower minimum/maximum). Subset check passes."""
    cap = _capability(parameter_schema=_BROAD_CAPABILITY_SCHEMA)
    method = _method(capability_id=cap.id)
    narrow_schema = {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {"type": "number", "minimum": 10, "maximum": 30},
            "filter_material": {"type": "string", "enum": ["Cu", "Al"]},
        },
        "required": ["energy"],
    }
    events = decide(
        state=method,
        command=UpdateMethodParametersSchema(method_id=method.id, parameters_schema=narrow_schema),
        capability=cap,
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].parameters_schema == narrow_schema


@pytest.mark.unit
def test_decide_rejects_method_property_not_in_capability() -> None:
    """Method declares a property the Capability doesn't have. 409."""
    cap = _capability(parameter_schema=_BROAD_CAPABILITY_SCHEMA)
    method = _method(capability_id=cap.id)
    rogue_schema = {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {"type": "number"},
            "rogue_param": {"type": "string"},
        },
    }
    with pytest.raises(MethodParametersNotSubsetError) as exc_info:
        decide(
            state=method,
            command=UpdateMethodParametersSchema(
                method_id=method.id, parameters_schema=rogue_schema
            ),
            capability=cap,
            now=_NOW,
        )
    assert "rogue_param" in exc_info.value.reason


@pytest.mark.unit
def test_decide_rejects_type_mismatch() -> None:
    """Method declares energy as string but Capability declares number. 409."""
    cap = _capability(parameter_schema=_BROAD_CAPABILITY_SCHEMA)
    method = _method(capability_id=cap.id)
    bad_type_schema = {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {"energy": {"type": "string"}},
    }
    with pytest.raises(MethodParametersNotSubsetError) as exc_info:
        decide(
            state=method,
            command=UpdateMethodParametersSchema(
                method_id=method.id, parameters_schema=bad_type_schema
            ),
            capability=cap,
            now=_NOW,
        )
    assert "type mismatch" in exc_info.value.reason


@pytest.mark.unit
def test_decide_rejects_widened_enum() -> None:
    """Method's enum includes a value not in Capability's enum. 409."""
    cap = _capability(parameter_schema=_BROAD_CAPABILITY_SCHEMA)
    method = _method(capability_id=cap.id)
    widened_schema = {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "filter_material": {"type": "string", "enum": ["Cu", "Al", "Mo", "Au"]},
        },
    }
    with pytest.raises(MethodParametersNotSubsetError) as exc_info:
        decide(
            state=method,
            command=UpdateMethodParametersSchema(
                method_id=method.id, parameters_schema=widened_schema
            ),
            capability=cap,
            now=_NOW,
        )
    assert "enum" in exc_info.value.reason


@pytest.mark.unit
def test_decide_rejects_widened_maximum() -> None:
    """Method's maximum exceeds Capability's maximum. 409."""
    cap = _capability(parameter_schema=_BROAD_CAPABILITY_SCHEMA)
    method = _method(capability_id=cap.id)
    widened_schema = {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {"type": "number", "minimum": 5, "maximum": 100},
        },
    }
    with pytest.raises(MethodParametersNotSubsetError) as exc_info:
        decide(
            state=method,
            command=UpdateMethodParametersSchema(
                method_id=method.id, parameters_schema=widened_schema
            ),
            capability=cap,
            now=_NOW,
        )
    assert "maximum" in exc_info.value.reason


@pytest.mark.unit
def test_decide_rejects_required_property_unknown_to_capability() -> None:
    """Method requires a property Capability doesn't declare. 409."""
    cap = _capability(parameter_schema=_BROAD_CAPABILITY_SCHEMA)
    method = _method(capability_id=cap.id)
    bad_required_schema = {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {"energy": {"type": "number"}},
        "required": ["energy", "phantom_field"],
    }
    with pytest.raises(MethodParametersNotSubsetError) as exc_info:
        decide(
            state=method,
            command=UpdateMethodParametersSchema(
                method_id=method.id, parameters_schema=bad_required_schema
            ),
            capability=cap,
            now=_NOW,
        )
    # The decider may flag either the rogue property OR the required entry first;
    # both are valid subset violations.
    assert "phantom_field" in exc_info.value.reason


@pytest.mark.unit
def test_decide_skips_subset_check_when_capability_has_no_parameter_schema() -> None:
    """When the bound Capability declares no parameter_schema, the
    contract is unconstrained — any well-formed Method schema is
    accepted. Pinned because Capability.parameter_schema is OPTIONAL
    at define_capability and we don't want missing-contract to lock
    out Method schemas."""
    cap = _capability(parameter_schema=None)
    method = _method(capability_id=cap.id)
    any_schema = {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {"anything": {"type": "string"}},
    }
    events = decide(
        state=method,
        command=UpdateMethodParametersSchema(method_id=method.id, parameters_schema=any_schema),
        capability=cap,
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_skips_subset_check_when_method_has_no_capability_id() -> None:
    """Pre-6l-strict Method fixtures (legacy MethodDefined events with
    no capability_id) gracefully skip the subset check. Handler builds
    context with `capability=None`. Pinned for legacy stream-replay
    compat (the additive-state pattern survives the 6l-strict flip)."""
    method = _method(capability_id=None)
    any_schema = {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {"anything": {"type": "string"}},
    }
    events = decide(
        state=method,
        command=UpdateMethodParametersSchema(method_id=method.id, parameters_schema=any_schema),
        capability=None,
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_skips_subset_check_when_method_clears_schema_to_none() -> None:
    """Clearing the schema (parameters_schema=None) is always allowed
    regardless of the Capability's contract. Pinned because the
    subset check needs SOMETHING on both sides to compare."""
    cap = _capability(parameter_schema=_BROAD_CAPABILITY_SCHEMA)
    method = _method(
        capability_id=cap.id,
        parameters_schema={"$schema": _DRAFT, "type": "object"},
    )
    events = decide(
        state=method,
        command=UpdateMethodParametersSchema(method_id=method.id, parameters_schema=None),
        capability=cap,
        now=_NOW,
    )
    assert len(events) == 1
    assert events[0].parameters_schema is None
