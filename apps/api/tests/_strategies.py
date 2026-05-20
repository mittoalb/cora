"""Shared Hypothesis strategies for property-based tests across BCs.

Lives at the `tests/` root (sibling to `_pg.py`) so any test tier
can import without one tier reaching into another's conftest.
Extracted at n=2 BCs (Access + Trust Zone) per the testing-expansion
research-memo's rule-of-three threshold ([[project-testing-expansion-
research]] Corpus 1, Ogooreck precedent).

Conventions adopted from the Hypothesis maintainers
(https://hypothesis.works/articles/hypothesis-pytest-fixtures/):

  - Strategies are MODULE-LEVEL composites, NOT pytest fixtures.
    Fixtures run once per test and fight Hypothesis's shrinking; module-
    level strategies compose freely and shrink correctly.
  - NO use of `st.register_type_strategy` for domain types — different
    BCs may collide on common type names (`Id`, `Name`). Per-BC strategy
    modules add their own; this kernel covers cross-BC primitives only.

When this grows enough that per-BC strategy collections want their own
home (e.g. `tests/_strategies/access.py` for `actor_kinds()` /
`actors()`), promote this file to a package (`tests/_strategies/__init__.py`
+ per-BC submodules) and re-export the kernel from the package root.
"""

from __future__ import annotations

from datetime import UTC

from hypothesis import strategies as st

# Printable ASCII without whitespace (codepoints 0x21-0x7E). Matches the
# alphabet every existing PBT file rebuilds inline; used for `name`,
# `signal_type`, `subject`, `issuer`, port-name fields. Whitespace is
# excluded so generated values survive `.strip()` canonicalization
# without `assume(name == name.strip())` shrinking complaints.
_PRINTABLE_ASCII = st.characters(min_codepoint=0x21, max_codepoint=0x7E)


def printable_ascii_text(*, min_size: int = 1, max_size: int) -> st.SearchStrategy[str]:
    """Bounded ASCII text, no whitespace. Survives `.strip()` round-trip.

    Use for free-form name / display-text / signal-type fields whose
    domain constraint is "non-empty, length-bounded, trimmed at the
    edge."
    """
    return st.text(alphabet=_PRINTABLE_ASCII, min_size=min_size, max_size=max_size)


def aware_datetimes() -> st.SearchStrategy:
    """UTC-tz-aware datetimes. Matches what the Clock port returns in
    production (datetime.now(tz=UTC)) and what events carry on the wire.

    Use in serialization round-trip tests, where `datetime.isoformat()` /
    `datetime.fromisoformat()` round-tripping requires a tz; naive
    datetimes can silently lose precision or fail to round-trip across
    timezone-aware parsers.
    """
    return st.datetimes(timezones=st.just(UTC))
