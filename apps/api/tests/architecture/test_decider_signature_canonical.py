"""Deciders follow the canonical signature shape.

Per ``docs/reference/layout.md`` Naming section:

  - Create-style: ``decide(state, command, *, now, new_id) -> list[<E>]``
  - Update-style: ``decide(state, command, *, now) -> list[<E>]``

The first two positional parameters are exactly ``state`` and ``command``.
Cross-aggregate context, ``now``, ``new_id``, and slice-specific extras
all go after the ``*`` marker as keyword-only.

Cross-aggregate-multi-stream slices return a frozen dataclass that wraps
per-stream event lists (``MembershipEvents``, ``ClearanceAmendmentEvents``,
``StartRunEvents``) instead of a single ``list[<E>]``; the handler then
hands the named lists to ``EventStore.append_streams`` as one atomic
batch. The shape is documented at the slice and not pinned here.

This fitness function pins two properties:

  1. ``decide`` is defined as a top-level function in the file.
  2. Its positional args are exactly ``[state, command]``.

``WIP_DECIDERS`` is an explicit allowlist for slices whose signature
diverges intentionally or is mid-renovation. Each entry MUST cite the
finding and the phase that will close it; reviewers should reject
additions that don't.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

# Each entry cites the cross-package consistency audit (2026-05-22)
# finding and the phase that will fix it. Empty entries when the
# corresponding finding ships.
#
# Note on B7: promote_caution_proposal is NOT in this allowlist even
# though it's a B7 violator. Its signature IS `(state, command)` which
# the canonical-args check accepts; the B7 issue is the return type
# (ProposedCautionView, not list[E]). Return type is intentionally not
# pinned by this test (see module docstring). Phase β addresses the
# return-shape rewrite via manual review.
WIP_DECIDERS: frozenset[str] = frozenset(
    {
        # B7: returns DecisionRegistered directly + kwargs-only signature.
        # Phase β will conform to (state, command, *, now, new_id) shape.
        "cora.agent.features.re_debrief_run.decider",
        # D10: `context` declared positional rather than keyword-only.
        # Phase ζ will move them after the `*` marker.
        "cora.subject.features.mount_subject.decider",
        "cora.decision.features.register_decision.decider",
        "cora.data.features.register_dataset.decider",
    }
)


def _decider_files() -> list[Path]:
    tracked = tracked_python_files()
    out: list[Path] = []
    for bc in BCS:
        features = CORA_ROOT / bc / "features"
        out.extend(
            sorted(
                f
                for f in tracked
                if f.name == "decider.py"
                and f.parent.parent == features
                and not f.parent.name.startswith("_")
            )
        )
    return out


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _find_decide_function(tree: ast.Module) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "decide":
            return node
    return None


def _positional_arg_names(func: ast.FunctionDef) -> list[str]:
    return [a.arg for a in func.args.posonlyargs] + [a.arg for a in func.args.args]


@pytest.mark.architecture
@pytest.mark.parametrize("decider", _decider_files(), ids=_qualified)
def test_decide_signature_is_canonical(decider: Path) -> None:
    qualified = _qualified(decider)
    if qualified in WIP_DECIDERS:
        pytest.skip(f"{qualified} is in WIP_DECIDERS (mid-phase)")

    tree = ast.parse(decider.read_text())
    func = _find_decide_function(tree)
    assert func is not None, (
        f"{qualified}: no top-level `decide` function found. "
        "Every command/update decider exposes `decide(state, command, *, ...)`."
    )

    positional = _positional_arg_names(func)
    assert positional == ["state", "command"], (
        f"{qualified}: decide() positional args are {positional!r}, "
        "expected exactly ['state', 'command']. Move extras after the `*` "
        "marker (per docs/reference/layout.md Naming section)."
    )


@pytest.mark.architecture
def test_wip_deciders_still_violate() -> None:
    """``WIP_DECIDERS`` entries must still have non-canonical signatures.

    Drift catcher: once a slice is conformed to ``(state, command, *, ...)``,
    its WIP entry becomes dead weight. Re-running the detector here forces
    the allowlist entry to be removed alongside the fix.
    """
    for qualified in WIP_DECIDERS:
        parts = qualified.split(".")
        assert parts[0] == "cora", f"{qualified}: must start with 'cora.'"
        path = CORA_ROOT.joinpath(*parts[1:]).with_suffix(".py")
        assert path.is_file(), f"WIP_DECIDERS entry {qualified}: file no longer exists; remove it"
        tree = ast.parse(path.read_text())
        func = _find_decide_function(tree)
        assert func is not None, (
            f"WIP_DECIDERS entry {qualified}: decide function gone; remove allowlist entry"
        )
        positional = _positional_arg_names(func)
        assert positional != ["state", "command"], (
            f"WIP_DECIDERS entry {qualified}: signature is now canonical "
            f"({positional!r}); remove allowlist entry"
        )
