"""Domain error class names follow the canonical taxonomy.

Per ``docs/reference/patterns.md`` Rejections table, domain errors in
``aggregates/<aggregate>/state.py`` follow one of four shapes:

  - ``Invalid<X>Error``         (validation, 400)
  - ``<X>NotFoundError``        (not found, 404)
  - ``<X>AlreadyExistsError``   (already exists, 409)
  - ``<X>Cannot<Verb>Error``    (state transition, 409)

This fitness function pins three concrete anti-patterns the
2026-05-22 audit (D7, D8) found accumulating:

  - ``*Missing*Error``                 →  use ``<X>NotFoundError``
  - ``Duplicate*Error``                →  use ``<X>AlreadyExistsError``
  - ``*AlreadyDeactivatedError``       →  use ``<X>CannotDeactivateError``

The fuzzier audit items (``AgentDeactivatedError``,
``AgentNotSeededError``) are state-predicate names that lack a clean
regex; Phase ε addresses them via manual review.

``GRANDFATHERED_NAMES`` is the explicit work-tracker for known
violators awaiting Phase ε. Each entry MUST cite the finding.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


_FORBIDDEN_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r".*Missing\w*Error$"), "use <X>NotFoundError suffix"),
    (re.compile(r"^Duplicate\w+Error$"), "use <X>AlreadyExistsError suffix"),
    (
        re.compile(r"^\w+AlreadyDeactivatedError$"),
        "use <X>CannotDeactivateError (state-transition family)",
    ),
)


# Entries are "<qualified-module>:ClassName". Each cites the audit
# finding; Phase ε removes the entry alongside the rename.
GRANDFATHERED_NAMES: frozenset[str] = frozenset(
    {
        # D7: cross-aggregate NotFound errors using *Missing* suffix.
        "cora.data.aggregates.dataset.state:ProducingRunMissingError",
        "cora.data.aggregates.dataset.state:LinkedSubjectMissingError",
        "cora.data.aggregates.dataset.state:DerivedFromDatasetsMissingError",
        "cora.decision.aggregates.decision.state:DeciderActorMissingError",
        "cora.decision.aggregates.decision.state:ParentDecisionMissingError",
        # D8: Already*Deactivated suffix used for state-transition semantics.
        "cora.access.aggregates.actor.state:ActorAlreadyDeactivatedError",
    }
)


def _state_files() -> list[Path]:
    """Tracked ``state.py`` files under ``<bc>/aggregates/<agg>/state.py``."""
    return sorted(
        f
        for f in tracked_python_files()
        if f.name == "state.py"
        and f.parent.parent.name == "aggregates"
        and f.parent.parent.parent.parent == CORA_ROOT
    )


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _error_class_names(tree: ast.Module) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name.endswith("Error"):
            out.append((node.lineno, node.name))
    return out


@pytest.mark.architecture
@pytest.mark.parametrize("state_file", _state_files(), ids=_qualified)
def test_error_names_follow_canonical_taxonomy(state_file: Path) -> None:
    qualified_module = _qualified(state_file)
    tree = ast.parse(state_file.read_text())
    violations: list[str] = []
    for lineno, name in _error_class_names(tree):
        key = f"{qualified_module}:{name}"
        if key in GRANDFATHERED_NAMES:
            continue
        for pattern, guidance in _FORBIDDEN_PATTERNS:
            if pattern.match(name):
                violations.append(f"line {lineno}: {name} — {guidance}")
                break
    assert not violations, (
        f"{qualified_module} declares error(s) with non-canonical "
        f"names:\n  " + "\n  ".join(violations) + "\n"
        "Per docs/reference/patterns.md Rejections, domain errors use "
        "Invalid<X>Error / <X>NotFoundError / <X>AlreadyExistsError / "
        "<X>Cannot<Verb>Error."
    )


@pytest.mark.architecture
def test_grandfathered_names_still_match_forbidden_pattern() -> None:
    """``GRANDFATHERED_NAMES`` entries must still match a forbidden regex.

    Drift catcher: once Phase ε renames a class to the canonical form,
    its allowlist entry becomes dead weight. Re-running the regex check
    here forces the entry to be removed alongside the rename.
    """
    for entry in GRANDFATHERED_NAMES:
        qualified, _, cls = entry.partition(":")
        parts = qualified.split(".")
        assert parts[0] == "cora", f"{entry}: must start with 'cora.'"
        path = CORA_ROOT.joinpath(*parts[1:]).with_suffix(".py")
        assert path.is_file(), f"{entry}: file no longer exists; remove allowlist entry"
        tree = ast.parse(path.read_text())
        names = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
        assert cls in names, (
            f"{entry}: class no longer defined; remove allowlist entry (Phase ε rename shipped)"
        )
        assert any(pattern.match(cls) for pattern, _ in _FORBIDDEN_PATTERNS), (
            f"{entry}: class name no longer matches a forbidden pattern; remove allowlist entry"
        )
