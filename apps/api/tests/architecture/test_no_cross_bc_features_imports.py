"""Rule 2: a BC may not import from a sibling BC's `features.*` namespace.

Mirrors the rule in the header of `apps/api/tach.toml`:

  > A BC may only reach into a sibling BC through that sibling's
  > `aggregates.*` namespace (the read-side public surface).
  > Never through `features.*` (sibling slice handlers).

Tach is the primary enforcer, but tach.toml is itself editable; a
contributor running `tach sync` after adding a violating import would
silently widen the allowlist instead of seeing a failure. This test
is the defense-in-depth: it walks every `cora.<bc>/**/*.py` with AST
and asserts no `from cora.<other_bc>.features.*` or
`import cora.<other_bc>.features.*` appears.

Exceptions:

  - `cora.api/*.py` is the composition root; it's allowed to import
    every BC's `features.*` (it wires routes and tools). This is
    documented in `tach.toml`.
  - Same-BC imports (`cora.<bc>.<x>` importing `cora.<bc>.features.*`)
    are intra-BC and always allowed.
  - Tests under `apps/api/tests/` are excluded from this test (and
    from tach) by design; integration / contract tests legitimately
    drive sibling slice handlers to seed cross-BC state.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT

_BCS: frozenset[str] = frozenset(BCS)


def _bc_python_files() -> list[Path]:
    """Every `.py` file under `cora/<bc>/` for every BC."""
    out: list[Path] = []
    for bc in BCS:
        bc_root = CORA_ROOT / bc
        if not bc_root.is_dir():
            continue
        out.extend(sorted(bc_root.rglob("*.py")))
    return out


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _owning_bc(path: Path) -> str:
    """Which BC owns this file (the path segment immediately under `cora/`)."""
    return path.relative_to(CORA_ROOT).parts[0]


def _imported_modules(tree: ast.AST) -> list[tuple[int, str]]:
    """Every `import X` / `from X import ...` in the file, as (lineno, module)."""
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append((node.lineno, node.module))
    return out


def _is_cross_bc_features_import(module: str, owning_bc: str) -> bool:
    """True if `module` is `cora.<other_bc>.features...` where other != owning."""
    parts = module.split(".")
    if len(parts) < 3:
        return False
    if parts[0] != "cora":
        return False
    target_bc = parts[1]
    if target_bc not in _BCS:
        return False
    if target_bc == owning_bc:
        return False
    return parts[2] == "features"


@pytest.mark.architecture
@pytest.mark.parametrize("path", _bc_python_files(), ids=_qualified)
def test_no_cross_bc_features_import(path: Path) -> None:
    """Modules under `cora.<bc>` never import `cora.<other_bc>.features.*`."""
    owning_bc = _owning_bc(path)
    tree = ast.parse(path.read_text())
    violations: list[str] = []
    for lineno, module in _imported_modules(tree):
        if _is_cross_bc_features_import(module, owning_bc):
            violations.append(f"line {lineno}: {module}")
    assert not violations, (
        f"{_qualified(path)} reaches into a sibling BC's features.* namespace:\n  "
        + "\n  ".join(violations)
        + "\n"
        "Cross-BC writes use the sibling's `aggregates.*` event types + VOs and write "
        "via `EventStore.append_streams` (see `define_agent/handler.py` and "
        "`promote_caution_proposal/handler.py` for examples)."
    )
