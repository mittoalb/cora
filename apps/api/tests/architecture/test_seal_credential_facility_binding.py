"""SEC-FED-01 (Slice 6 Sub-Slice C structural fold): Seal initialise /
rotate deciders must check that the candidate credential id is a member
of the bound Facility's `trust_anchor_credential_ids` set so a peer
facility's Credential cannot be installed in another facility's Seal
slot. Without the check, the `CredentialLookup` port returns rows
across facilities and a caller with write access to one facility could
bind a foreign facility's key into their own seal.

Pre-Sub-Slice-C this fitness pinned a string-equality comparison
between `<credential>.facility_id` and the seal's `command.facility_id`
or `state.facility_id`. After Sub-Slice C the comparison is structural:
the decider tests `command.<credential_id> in
self_facility.trust_anchor_credential_ids` (or similarly named
parameters).

The fitness function is structural, not behavioural: it AST-walks each
decider and asserts the file contains at least one `Compare` node with
an `In` operator whose left operand is a credential-id attribute access
(`command.online_credential_id` / `command.offline_credential_id` /
`command.new_online_credential_id`) and whose right operand is an
attribute access `<facility_param>.trust_anchor_credential_ids`. The
same regression will tip the integration test suite, but the AST pin
catches it at review time (drift in a decider is loud) and survives
refactors of the test harness.

Mirrors the `test_decider_purity.py` AST-walker pattern (forbidden
attribute calls vs forbidden imports); here we ASSERT a required
shape rather than forbid one.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT

if TYPE_CHECKING:
    from pathlib import Path

_DECIDERS: tuple[Path, ...] = (
    CORA_ROOT / "federation" / "features" / "initialize_seal" / "decider.py",
    CORA_ROOT / "federation" / "features" / "rotate_seal_online_key" / "decider.py",
)

_CREDENTIAL_ID_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "online_credential_id",
        "offline_credential_id",
        "new_online_credential_id",
    }
)

_TRUST_ANCHOR_ATTRIBUTE = "trust_anchor_credential_ids"


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _is_command_credential_id(node: ast.AST) -> bool:
    """`node` is `command.<one of the credential id attributes>`."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr in _CREDENTIAL_ID_ATTRIBUTES
        and isinstance(node.value, ast.Name)
        and node.value.id == "command"
    )


def _is_trust_anchor_set(node: ast.AST) -> bool:
    """`node` is `<facility_param>.trust_anchor_credential_ids` for some
    handler-injected facility-lookup parameter (bare name)."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == _TRUST_ANCHOR_ATTRIBUTE
        and isinstance(node.value, ast.Name)
    )


def _has_trust_anchor_membership_check(tree: ast.AST) -> bool:
    """Some `ast.Compare` in `tree` has an `In` op pairing a command
    credential id with a facility's trust_anchor_credential_ids."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not node.ops:
            continue
        if not all(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
            continue
        operands: list[ast.AST] = [node.left, *node.comparators]
        has_credential = any(_is_command_credential_id(op) for op in operands)
        has_trust_anchor = any(_is_trust_anchor_set(op) for op in operands)
        if has_credential and has_trust_anchor:
            return True
    return False


@pytest.mark.architecture
@pytest.mark.parametrize("decider", _DECIDERS, ids=_qualified)
def test_seal_decider_checks_trust_anchor_membership(decider: Path) -> None:
    """The decider tests command.<credential_id> set-membership against
    the bound facility's trust_anchor_credential_ids."""
    assert decider.exists(), (
        f"Decider not found: {decider}. The SEC-FED-01 pin must move with "
        "the decider; update `_DECIDERS` if the slice was renamed."
    )
    tree = ast.parse(decider.read_text())
    assert _has_trust_anchor_membership_check(tree), (
        f"{_qualified(decider)} does not test any of "
        f"{{{', '.join(sorted(_CREDENTIAL_ID_ATTRIBUTES))}}} for membership "
        "in <facility>.trust_anchor_credential_ids.\n"
        "SEC-FED-01: without this binding, a caller with write access to one "
        "facility's Seal could install a peer facility's Credential as their "
        "online or offline key. Add an explicit "
        "`if command.<credential_id> not in self_facility."
        "trust_anchor_credential_ids: raise ...` guard alongside the "
        "purpose / status checks."
    )
