"""Open-scheme anti-corruption-ref `Identifier(scheme, value)` value object.

Shared free-form-scheme pair for upstream-deferred concepts CORA does NOT
model as first-class aggregates (proposal, btr, lab visit, session, cycle,
and so on). Carrier aggregates hold `frozenset[Identifier]` fields named
`external_refs` and round-trip the typed VO through
`{"scheme": str, "value": str}` payload dicts.

This VO absorbs ONLY the open-scheme anti-corruption-ref axis. PID-tier
and 3-tuple shapes stay bespoke at their carrier aggregates:

  - `PersistentIdentifier` (closed-enum scheme {DOI, HANDLE}, per-aggregate
    `MalformedPersistentIdentifierError`) and `AlternateIdentifier` (closed
    3-value kind enum, pre-committed to gain PIDINST 13.2
    `alternateIdentifierName` as a third field) live on Asset and do NOT
    compose `Identifier`.
  - 3-tuple VOs (`Manufacturer`, `AssetOwner`, `Drawing`, `ScopeRef`,
    `ModelRef`) each carry a load-bearing third field and stay bespoke.
  - `DatasetChecksum` enforces a stricter 64-char lowercase-hex value
    invariant and stays bespoke.
  - `CalibrationSource` arms wrap typed intra-CORA UUIDs, not external
    (scheme, value) pairs.

Closed-vocabulary discipline lives on the CARRIER aggregate; the VO itself
keeps the scheme free-form. Per-aggregate closed-enum types MUST enforce
their closed-enum invariant at their OWN `__post_init__` BEFORE delegating
to any shared validator; the Identifier VO never sees the closed-enum
context.

Cross-reference [[project-identifier-vo-design]] for the locked shape, the
pre-pilot wire-key rename (`id -> value`), the deviation allowlist, and the
federation-readiness notes.
"""

from dataclasses import dataclass

IDENTIFIER_SCHEME_MAX_LENGTH = 50
IDENTIFIER_VALUE_MAX_LENGTH = 200


class InvalidIdentifierError(ValueError):
    """An Identifier's scheme or value is empty, whitespace-only, or too long.

    The `value` attribute carries the ORIGINAL untrimmed input so callers
    can diagnose whitespace-only rejections without losing the offending
    characters.
    """

    def __init__(self, field: str, value: str) -> None:
        super().__init__(f"Identifier {field} is invalid (got: {value!r})")
        self.field = field
        self.value = value


@dataclass(frozen=True, slots=True)
class Identifier:
    """Open-scheme identifier pair. Free-form scheme; per-site closed-enum
    discipline lives at the carrier aggregate, not on this VO."""

    scheme: str
    value: str

    def __post_init__(self) -> None:
        scheme_trimmed = self.scheme.strip()
        if not scheme_trimmed or len(scheme_trimmed) > IDENTIFIER_SCHEME_MAX_LENGTH:
            raise InvalidIdentifierError(field="scheme", value=self.scheme)
        value_trimmed = self.value.strip()
        if not value_trimmed or len(value_trimmed) > IDENTIFIER_VALUE_MAX_LENGTH:
            raise InvalidIdentifierError(field="value", value=self.value)
        object.__setattr__(self, "scheme", scheme_trimmed)
        object.__setattr__(self, "value", value_trimmed)


__all__ = [
    "IDENTIFIER_SCHEME_MAX_LENGTH",
    "IDENTIFIER_VALUE_MAX_LENGTH",
    "Identifier",
    "InvalidIdentifierError",
]
