"""Cross-BC `ExternalRef` value object for anti-corruption references.

`ExternalRef(scheme, id)` is the shared shape for upstream-deferred
concepts CORA does NOT model as first-class aggregates: proposal,
beam-time request, lab visit, session, cycle, and so on. Each carrier
BC (Run since 11a-c-3, Campaign since 6i-a) holds a
`frozenset[ExternalRef]` field on its aggregate state and round-trips
the typed VO through `{"scheme": str, "id": str}` payload dicts.

Hoisted at 6i-a per the design memo's instruction: the synthesis memo
and Campaign design memo both reference `ExternalRef` from Campaign +
Run + Clearance, so the third cross-BC reuse site fires the rule-of-
three. Prior to 6i-a the VO lived on Run's state module
(`cora.run.aggregates.run.state.ExternalRef`); Run BC's
`__init__.py` keeps a re-export of `ExternalRef` /
`InvalidExternalRefError` so existing import paths stay green.

## Bounds

  - `scheme`: 1-50 chars after trim. Common values: `proposal`,
    `btr`, `lab_visit`, `session`, `visit`, `cycle`.
  - `id`: 1-200 chars after trim. Facility-issued opaque string.

The bounds match Safety BC's `ExternalBinding(scheme, id)` so the
`(scheme, id)` pair round-trips cleanly between Run / Campaign
external_refs and Clearance bindings.
"""

from dataclasses import dataclass

EXTERNAL_REF_SCHEME_MAX_LENGTH = 50
EXTERNAL_REF_ID_MAX_LENGTH = 200


class InvalidExternalRefError(ValueError):
    """An ExternalRef's scheme or id is empty, whitespace-only, or too long.

    Mirrors Safety BC's `InvalidClearanceExternalBindingError` shape
    (same field bounds) so the (scheme, id) pair round-trips cleanly
    between carrier-BC external_refs and Clearance.bindings.
    """

    def __init__(self, field_name: str, value: str, max_length: int) -> None:
        super().__init__(
            f"ExternalRef {field_name} must be 1-{max_length} chars after trimming (got: {value!r})"
        )
        self.field_name = field_name
        self.value = value
        self.max_length = max_length


@dataclass(frozen=True)
class ExternalRef:
    """Anti-corruption ref to an upstream-deferred concept CORA does NOT model.

    Same shape as Safety BC's `ExternalBinding(scheme, id)` so a
    carrier's `external_refs` round-trip cleanly against
    `Clearance.bindings` for future ExternalBinding-based clearance
    coverage gating (deferred per `[[project_safety_clearance_design]]`
    watch item).

    Common schemes: `proposal` / `btr` / `lab_visit` / `session` /
    `visit` / `cycle`.
    """

    scheme: str
    id: str

    def __post_init__(self) -> None:
        for attr_name, value, max_length in (
            ("scheme", self.scheme, EXTERNAL_REF_SCHEME_MAX_LENGTH),
            ("id", self.id, EXTERNAL_REF_ID_MAX_LENGTH),
        ):
            trimmed = value.strip()
            if not trimmed or len(trimmed) > max_length:
                raise InvalidExternalRefError(attr_name, value, max_length)
            object.__setattr__(self, attr_name, trimmed)


__all__ = [
    "EXTERNAL_REF_ID_MAX_LENGTH",
    "EXTERNAL_REF_SCHEME_MAX_LENGTH",
    "ExternalRef",
    "InvalidExternalRefError",
]
