"""Direct `Kernel(...)` construction is restricted to the production
primitives in `cora/infrastructure/deps.py`.

The two `make_postgres_kernel` / `make_inmemory_kernel` primitives in
`cora/infrastructure/deps.py` are the only place production constructs
a Kernel. Tests call those primitives via thin wrappers
(`tests/unit/_helpers.py::build_deps` for in-memory,
`tests/integration/_helpers.py::build_postgres_deps` for Postgres-
backed), so the wrappers themselves no longer carry a direct
`Kernel(...)` call.

Adding a required `Kernel` field now lands in exactly two function
bodies (the two primitives) instead of every callsite individually.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import tracked_python_files, tracked_test_files

# tests/architecture/test_kernel_construction_single_site.py -> apps/api/
_API_ROOT = Path(__file__).resolve().parents[2]

# The single allowed Kernel-construction site. Paths are relative to
# apps/api/. The meta-test `test_allowlist_files_actually_construct_kernel`
# below verifies each entry still contains a Kernel(...) call so the
# allowlist cannot accumulate stale entries.
_ALLOWLIST: frozenset[str] = frozenset(
    {
        "src/cora/infrastructure/deps.py",
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
    scan inside the parametrized test confirms; false positives (for example
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


@pytest.mark.architecture
@pytest.mark.parametrize("relative", sorted(_ALLOWLIST))
def test_allowlist_files_actually_construct_kernel(relative: str) -> None:
    """Every allowlisted file MUST actually contain a `Kernel(...)` call
    site. Without this drift catcher, an allowlisted file that stops
    constructing Kernel directly (because the call moved out, was
    refactored into a helper, etc.) is silently retained: the primary
    test's substring-based candidate filter never lifts the file into
    its check, so its `lines, ...` assertion never fires.
    """
    path = _API_ROOT / relative
    assert path.is_file(), f"{relative} no longer exists; prune from _ALLOWLIST"
    tree = ast.parse(path.read_text(), filename=str(path))
    lines = _kernel_call_lines(tree)
    assert lines, (
        f"{relative} is on _ALLOWLIST but no longer contains a "
        f"`Kernel(...)` construction site. Either restore the direct "
        f"construction or prune the allowlist entry."
    )
