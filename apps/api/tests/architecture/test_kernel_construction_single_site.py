"""Direct `Kernel(...)` construction is restricted to one production site
+ the integration-test helper.

The two `make_postgres_kernel` / `make_inmemory_kernel` primitives in
`cora/infrastructure/deps.py` are the only place production constructs
a Kernel. Tests call them via thin wrappers: `tests/unit/_helpers.py::
build_deps` (in-memory) and `tests/integration/_helpers.py::
build_postgres_deps` (Postgres-backed).

This test scans `src/` and `tests/integration/` only:

  - `src/`: forbid direct `Kernel(...)` outside the single allowed
    site, `cora/infrastructure/deps.py`.
  - `tests/integration/`: forbid direct `Kernel(...)` outside the
    single allowed site, `tests/integration/_helpers.py`.

`tests/unit/` is INTENTIONALLY out of scope. Per the
`tests/unit/_helpers.py::build_deps` docstring, ~35 unit-test files
still define their own per-BC `_build_deps` function (54 instances
pre-consolidation). Migration to the shared helper is opportunistic;
this test would otherwise generate a 35-entry allowlist that
documents nothing the helper docstring doesn't already say.

When a unit-test file migrates, it picks up the single-site discipline
transitively through the helper's call to `make_inmemory_kernel`. New
unit-test files SHOULD use `build_deps` from day one.
"""

import ast
from pathlib import Path

import pytest

# tests/architecture/test_kernel_construction_single_site.py -> apps/api/
_API_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _API_ROOT / "src"
_INTEGRATION_TESTS = _API_ROOT / "tests" / "integration"

# The single allowed Kernel-construction sites in each scanned tree.
# Paths are relative to apps/api/.
_ALLOWLIST: frozenset[str] = frozenset(
    {
        "src/cora/infrastructure/deps.py",
        "tests/integration/_helpers.py",
    }
)


def _python_files() -> list[Path]:
    """All Python files under src/ and tests/integration/. Excludes
    __pycache__ and .venv. tests/unit/ is intentionally not scanned
    (see module docstring)."""
    out: list[Path] = []
    for root in (_SRC_ROOT, _INTEGRATION_TESTS):
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.py")):
            if "__pycache__" in p.parts or ".venv" in p.parts:
                continue
            out.append(p)
    return out


def _candidate_files() -> list[Path]:
    """Files that mention `Kernel(` (cheap textual heuristic). The AST
    scan inside the parametrized test confirms; false positives (e.g.
    in comments) are harmless because the AST returns zero call sites.
    """
    return [p for p in _python_files() if "Kernel(" in p.read_text()]


def _qualified(p: Path) -> str:
    return str(p.relative_to(_API_ROOT))


def _kernel_call_lines(tree: ast.AST) -> list[int]:
    """Find every Call node whose func is a bare `Name("Kernel")`.

    Catches `Kernel(...)` and `Kernel(settings=..., ...)`. Does not
    catch `cora.infrastructure.kernel.Kernel(...)` (namespaced form);
    that form is unused today and would still fail tach's import
    contract if added in a forbidden module.
    """
    lines: list[int] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Kernel"
        ):
            lines.append(node.lineno)
    return lines


@pytest.mark.architecture
@pytest.mark.parametrize("py_file", _candidate_files(), ids=_qualified)
def test_kernel_constructed_only_in_allowed_sites(py_file: Path) -> None:
    qualified = _qualified(py_file)
    tree = ast.parse(py_file.read_text(), filename=str(py_file))
    lines = _kernel_call_lines(tree)

    if qualified in _ALLOWLIST:
        # Allowlisted file MUST still construct Kernel; otherwise the
        # allowlist is stale and should be pruned.
        assert lines, (
            f"{qualified} is allowlisted but no longer constructs Kernel(). "
            f"Prune the allowlist in {Path(__file__).name}."
        )
        return

    assert not lines, (
        f"{qualified}: direct Kernel(...) construction at line(s) "
        f"{sorted(lines)}. Use `make_postgres_kernel` or "
        f"`make_inmemory_kernel` from `cora.infrastructure.deps` (or, "
        f"in tests, the `build_postgres_deps` / `build_deps` wrappers "
        f"that call them). Adding a new field to Kernel should land in "
        f"exactly two function bodies, not N callsites."
    )


@pytest.mark.architecture
def test_allowlist_files_exist() -> None:
    """Drift catcher: if an allowlisted file moves or is renamed, fail loudly."""
    missing = [rel for rel in _ALLOWLIST if not (_API_ROOT / rel).is_file()]
    assert not missing, (
        f"Allowlist references files that no longer exist: {missing}. "
        f"Update the allowlist in {Path(__file__).name}."
    )
