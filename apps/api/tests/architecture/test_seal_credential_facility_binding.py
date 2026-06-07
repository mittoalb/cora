"""SEC-FED-01: Seal initialise / rotate deciders must compare the
resolved Credential's `facility_id` against the seal's facility
(either `command.facility_id` at genesis or `state.facility_id` on
rotation) so a peer facility's Credential cannot be installed in
another facility's Seal slot. Without the check, the
`CredentialLookup` port returns rows across facilities and a caller
with write access to one facility could bind a foreign facility's
key into their own seal.

The fitness function is structural, not behavioural: it AST-walks
each decider and asserts the file contains at least one comparison
expression that pairs a `<credential>.facility_id` reference (where
`<credential>` is one of the handler-injected credential parameters
listed in `_CREDENTIAL_PARAMETERS`) with either
`command.facility_id` or `state.facility_id`. The same regression
will tip the integration test suite, but the AST pin catches it at
review time (drift in a decider is loud) and survives refactors of
the test harness.

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

_CREDENTIAL_PARAMETERS: frozenset[str] = frozenset(
    {
        "online_credential",
        "offline_credential",
        "new_online_credential",
    }
)

_SEAL_FACILITY_OWNERS: frozenset[str] = frozenset({"command", "state"})


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _is_attr(node: ast.AST, owner: str, attr: str) -> bool:
    """`node` is the AST for `<owner>.<attr>` (a bare-name . attribute)."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == attr
        and isinstance(node.value, ast.Name)
        and node.value.id == owner
    )


def _is_credential_facility_id(node: ast.AST) -> bool:
    """`node` is `<credential>.facility_id` or `<credential>.facility_id.value`
    where `<credential>` is one of the handler-injected credential lookup
    results.

    The `.value` form is the post-Slice-3 shape from
    project_structural_scope_design: `CredentialLookupResult.facility_id`
    is a `FacilityCode` VO at the port surface, while the aggregate-stored
    `command.facility_id` / `state.facility_id` stay bare strings. Deciders
    extract `.value` inline at the comparison site to bridge.
    """
    # Direct `<credential>.facility_id` (pre-Slice-3 + decider intermediate use)
    if (
        isinstance(node, ast.Attribute)
        and node.attr == "facility_id"
        and isinstance(node.value, ast.Name)
        and node.value.id in _CREDENTIAL_PARAMETERS
    ):
        return True
    # `<credential>.facility_id.value` (post-Slice-3 FacilityCode VO comparison)
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "value"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "facility_id"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id in _CREDENTIAL_PARAMETERS
    )


def _is_seal_facility_id(node: ast.AST) -> bool:
    """`node` is `command.facility_id` or `state.facility_id`."""
    return any(_is_attr(node, owner, "facility_id") for owner in _SEAL_FACILITY_OWNERS)


def _has_facility_binding_comparison(tree: ast.AST) -> bool:
    """Some `ast.Compare` in `tree` pairs a credential facility_id with
    a seal facility_id (in either operand order, across any of the
    comparison's `comparators`)."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        operands: list[ast.AST] = [node.left, *node.comparators]
        has_credential = any(_is_credential_facility_id(op) for op in operands)
        has_seal = any(_is_seal_facility_id(op) for op in operands)
        if has_credential and has_seal:
            return True
    return False


@pytest.mark.architecture
@pytest.mark.parametrize("decider", _DECIDERS, ids=_qualified)
def test_seal_decider_binds_credential_facility(decider: Path) -> None:
    """The decider compares credential.facility_id against the seal's facility_id."""
    assert decider.exists(), (
        f"Decider not found: {decider}. The SEC-FED-01 pin must move with "
        "the decider; update `_DECIDERS` if the slice was renamed."
    )
    tree = ast.parse(decider.read_text())
    assert _has_facility_binding_comparison(tree), (
        f"{_qualified(decider)} does not compare any of "
        f"{{{', '.join(sorted(_CREDENTIAL_PARAMETERS))}}}.facility_id against "
        "command.facility_id or state.facility_id.\n"
        "SEC-FED-01: without this binding, a caller with write access to one "
        "facility's Seal could install a peer facility's Credential as their "
        "online or offline key. Add an explicit `if <credential>.facility_id "
        "!= <command|state>.facility_id: raise ...` guard alongside the "
        "purpose / status checks."
    )
