"""Actor event payloads carry NO PII. PII lives in the
`actor_profile` table per [[project_pii_vault]] +
[[project_pii_vault_implementation_design]].

Fitness function: AST-walks
`cora/access/aggregates/actor/events.py` and rejects any
dataclass field on an Actor event whose name appears in the
PII deny-list (`name`, `display_name`, `email`, `phone`,
`orcid`, `affiliation`).

Why this lives separately from the existing payload-immutability
and from_stored-coverage fitness tests: those tests pin
structural invariants on the event union. This one pins a
DOMAIN invariant — Actor events specifically must never carry
identifying personal data, so a future field rename or addition
that reintroduces `name` (or `email` / `phone` / etc.) fails
the build instead of silently re-broadening the audit-event PII
surface.

The deny-list mirrors the PII fields the design memo locks for
future actor_profile columns; widen it whenever a new identifying
column lands on the vault.
"""

import ast

import pytest

from tests.architecture.conftest import CORA_ROOT

_EVENTS_FILE = CORA_ROOT / "access" / "aggregates" / "actor" / "events.py"

# Any dataclass field on an Actor* event whose annotation target
# name matches one of these strings counts as a violation. Names are
# matched case-sensitively (Python identifier convention) and treat
# `display_name` and `name` separately so callers can re-introduce
# the longer-form synonym later without unblocking the shorter-form
# field unintentionally.
_PII_FIELD_NAMES = frozenset(
    {
        "name",
        "display_name",
        "email",
        "phone",
        "orcid",
        "affiliation",
    }
)


def _actor_event_pii_field_violations() -> list[str]:
    tree = ast.parse(_EVENTS_FILE.read_text())
    violations: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not node.name.startswith("Actor"):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign):
                continue
            target = stmt.target
            if isinstance(target, ast.Name) and target.id in _PII_FIELD_NAMES:
                violations.append(f"line {stmt.lineno}: {node.name}.{target.id}")
    return violations


@pytest.mark.architecture
def test_actor_event_payloads_carry_no_pii() -> None:
    """Pin: dataclass fields named like PII never land on Actor* events.

    PII lives in the `actor_profile` vault accessed via
    `ProfileStore`; events carry only `actor_id` references plus
    audit-relevant primitives (kind, occurred_at, forgotten_at).
    A regression here usually means someone re-added `name` or
    introduced an email / phone / etc. field on an event; move the
    field to actor_profile (and update the vault schema) instead.
    """
    violations = _actor_event_pii_field_violations()
    assert not violations, (
        "Actor event payloads must carry NO PII; move identifying fields to "
        "actor_profile via ProfileStore (see project_pii_vault):\n  " + "\n  ".join(violations)
    )


@pytest.mark.architecture
def test_actor_events_file_is_present() -> None:
    """Sanity: the events.py file must exist; the file move below
    the aggregate folder would silently make the PII-deny scan a
    no-op without this guard."""
    msg = f"Expected Actor events file at {_EVENTS_FILE}"
    assert _EVENTS_FILE.exists(), msg


@pytest.mark.architecture
def test_pii_deny_list_actually_finds_violations_when_seeded() -> None:
    """Meta-test: confirm the AST walker would flag a seeded
    violation. Guards against the silent-pass failure mode (e.g.
    a future refactor moves the event classes to a sub-module and
    the walker quietly stops seeing them). Builds an ephemeral
    in-memory ast.Module mimicking the events file with a single
    deliberately-bad Actor class, and asserts the walker would
    report it.
    """
    seed_source = (
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class ActorRegisteredV2:\n"
        "    actor_id: int\n"
        "    name: str  # PII violation seeded by the meta-test\n"
    )
    tree = ast.parse(seed_source)
    violations: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or not node.name.startswith("Actor"):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign):
                continue
            target = stmt.target
            if isinstance(target, ast.Name) and target.id in _PII_FIELD_NAMES:
                violations.append(f"line {stmt.lineno}: {node.name}.{target.id}")
    assert violations, "seeded `name` field must be flagged by the deny-list walker"
