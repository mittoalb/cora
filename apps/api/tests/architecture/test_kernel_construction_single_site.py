"""Direct `Kernel(...)` construction is restricted to two helpers + the
production primitives.

The two `make_postgres_kernel` / `make_inmemory_kernel` primitives in
`cora/infrastructure/deps.py` are the only place production constructs
a Kernel. Tests call them via thin wrappers: `tests/unit/_helpers.py::
build_deps` (in-memory) and `tests/integration/_helpers.py::
build_postgres_deps` (Postgres-backed).

This test scans `src/` and `tests/`:

  - `src/`: only `cora/infrastructure/deps.py` may construct Kernel.
  - `tests/integration/`: only `_helpers.py` may construct Kernel.
  - `tests/unit/`: only `_helpers.py` may construct Kernel, plus two
    legacy holdouts (see below).

## Allowlisted unit-test holdouts

Two unit-test files are allowlisted because their needs don't fit the
`make_inmemory_kernel` shape:

  - `tests/unit/test_idempotency_pruner.py` passes a non-None pool
    sentinel to test the pruner's pool-presence branch. Adding a
    `pool=` override to `make_inmemory_kernel` would clutter the
    primitive's contract for one test.

  - `tests/unit/access/test_list_actors_handler.py` predates the
    `build_deps` helper consolidation and constructs `Kernel(...)`
    directly with a custom `_DenyAllAuthorize`. Migration is possible
    but the file's auth-stub class structure differs from the canonical
    helper's; deferred until the test file is touched for other reasons.

Adding a required `Kernel` field now lands in exactly two function
bodies (the two primitives) instead of every callsite individually.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import tracked_python_files, tracked_test_files

# tests/architecture/test_kernel_construction_single_site.py -> apps/api/
_API_ROOT = Path(__file__).resolve().parents[2]

# The single allowed Kernel-construction sites in each scanned tree.
# Paths are relative to apps/api/.
_ALLOWLIST: frozenset[str] = frozenset(
    {
        "src/cora/infrastructure/deps.py",
        "tests/integration/_helpers.py",
        "tests/unit/_helpers.py",
    }
)


def _python_files() -> list[Path]:
    """All git-tracked Python files under src/ and tests/.

    Enumerates from git's tracked-file set rather than `rglob` so a
    half-staged refactor (existing Kernel(...) call edited-then-
    stashed, new construction site untracked) does not false-fail
    under pre-commit.
    """
    return sorted(tracked_python_files() | tracked_test_files())


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
