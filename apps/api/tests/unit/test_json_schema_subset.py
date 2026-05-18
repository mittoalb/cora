"""Unit tests for the shared constrained-subset checker.

`cora.infrastructure.json_schema_subset` was hoisted in 6g-a once the
third use site landed (Family schema declaration + Asset settings
union compile + Method parameters declaration). The two BC-specific
wrappers (`equipment.aggregates.capability.settings_validation` and
`recipe.aggregates.method.parameters_validation`) carry their own
deeper test suites for full $schema + jsonschema-rs coverage; this
file is the structural-subset contract pinned ONCE.
"""

from typing import Any

import pytest

from cora.infrastructure.json_schema_subset import (
    ALLOWED_SCHEMA_KEYS,
    DRAFT_2020_12_URI,
    check_subset,
)


class _SubsetError(ValueError):
    """Throwaway error class the test injects into check_subset."""


@pytest.mark.unit
def test_draft_uri_constant_pinned() -> None:
    """The Draft 2020-12 URI is the locked contract; both 5g-a and
    6g-a require schemas to declare exactly this string."""
    assert DRAFT_2020_12_URI == "https://json-schema.org/draft/2020-12/schema"


@pytest.mark.unit
def test_allowed_keys_pinned() -> None:
    """Anti-feature pin: widening this set is a deliberate decision
    (and every recursive-keyword addition needs a check_subset
    extension; see the module docstring). `unit` is a non-recursive
    annotation keyword whose value-shape is enforced separately by
    `json_schema_validation.validate_unit_annotations`."""
    assert (
        frozenset(
            {
                "$schema",
                "type",
                "required",
                "properties",
                "enum",
                "minimum",
                "maximum",
                "pattern",
                "unit",
            }
        )
        == ALLOWED_SCHEMA_KEYS
    )


@pytest.mark.unit
def test_check_subset_accepts_unit_annotation_opaque() -> None:
    """`unit` is in the allowlist; the subset checker treats its
    value as opaque and does NOT recurse into it. Shape validation
    of the annotation lives in
    `json_schema_validation.validate_unit_annotations`. This test
    pins the no-recurse contract: a `unit` value that looks
    schema-shaped but contains forbidden keywords must NOT raise here
    (the checker would only catch it if it recursed wrongly)."""
    schema = {
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "unit": {"oneOf": [{"type": "string"}]},
            }
        },
    }
    check_subset(schema, path="<root>", error_class=_SubsetError)


@pytest.mark.unit
def test_check_subset_passes_for_minimal_object() -> None:
    check_subset({"type": "object"}, path="<root>", error_class=_SubsetError)


@pytest.mark.unit
@pytest.mark.parametrize(
    "forbidden_key",
    ["$ref", "oneOf", "anyOf", "allOf", "not", "if", "additionalProperties"],
)
def test_check_subset_raises_caller_error_class_for_forbidden_keyword(
    forbidden_key: str,
) -> None:
    """Caller's error class is what's surfaced — not a generic
    ValueError from the shared helper."""
    schema: dict[str, Any] = {"type": "object", forbidden_key: True}
    with pytest.raises(_SubsetError) as exc_info:
        check_subset(schema, path="<root>", error_class=_SubsetError)
    assert "forbidden keyword" in str(exc_info.value)
    assert forbidden_key in str(exc_info.value)


@pytest.mark.unit
def test_check_subset_recurses_into_properties() -> None:
    """Forbidden keywords nested inside properties values must also
    raise — the recursion is the pin that prevents shallow holes."""
    schema = {"type": "object", "properties": {"x": {"oneOf": [{"type": "number"}]}}}
    with pytest.raises(_SubsetError) as exc_info:
        check_subset(schema, path="<root>", error_class=_SubsetError)
    assert "properties.x" in str(exc_info.value)


@pytest.mark.unit
def test_check_subset_rejects_non_dict_properties() -> None:
    schema = {"type": "object", "properties": ["a", "b"]}
    with pytest.raises(_SubsetError) as exc_info:
        check_subset(schema, path="<root>", error_class=_SubsetError)
    assert "must be a dict" in str(exc_info.value)


@pytest.mark.unit
def test_check_subset_rejects_non_dict_property_value() -> None:
    schema = {"type": "object", "properties": {"x": "not-a-schema"}}
    with pytest.raises(_SubsetError) as exc_info:
        check_subset(schema, path="<root>", error_class=_SubsetError)
    assert "must be a schema dict" in str(exc_info.value)


@pytest.mark.unit
def test_check_subset_path_is_threaded_through_recursion() -> None:
    """Caller-friendly diagnostics: the path string in the error
    message reflects the recursion depth."""
    schema = {
        "type": "object",
        "properties": {
            "outer": {
                "type": "object",
                "properties": {"inner": {"oneOf": [{"type": "number"}]}},
            }
        },
    }
    with pytest.raises(_SubsetError) as exc_info:
        check_subset(schema, path="<root>", error_class=_SubsetError)
    assert "properties.outer.properties.inner" in str(exc_info.value)
