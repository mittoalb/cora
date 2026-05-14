"""Integration tests must construct Kernel via `build_postgres_deps`.

Phase B (Kernel parity factory) consolidates Postgres-backed Kernel
construction in `tests/integration/_helpers.py::build_postgres_deps`.
Direct `Kernel(...)` construction in `tests/integration/` would
re-introduce the wiring drift Phase B closed: a new required `Kernel`
field would need to be added to N test files individually instead of
to one factory.

The `tests/unit/_helpers.py::build_deps` helper enforces the same
discipline for unit tests, but unit tests are allowed two documented
holdouts (`test_idempotency_pruner.py` for custom Settings,
`test_list_actors_handler.py` for a pool-presence smoke). Integration
tests have no such holdouts at landing time; the test below allows the
helper module itself plus the integration `conftest.py` to construct
Kernel-adjacent things, and rejects everything else.
"""

import ast
from pathlib import Path

import pytest

# tests/architecture/test_integration_kernel_factory.py -> apps/api/
_API_ROOT = Path(__file__).resolve().parents[2]
_INTEGRATION_DIR = _API_ROOT / "tests" / "integration"

# Files in tests/integration/ that are permitted to call `Kernel(...)`
# directly. The helper module is the canonical factory site; conftest
# does not currently call Kernel but is whitelisted in case a future
# fixture needs it.
_ALLOWED = frozenset({"_helpers.py", "conftest.py"})


def _integration_test_files() -> list[Path]:
    if not _INTEGRATION_DIR.is_dir():
        return []
    return sorted(p for p in _INTEGRATION_DIR.glob("test_*.py") if p.name not in _ALLOWED)


def _qualified(p: Path) -> str:
    return "tests.integration." + p.with_suffix("").name


def _kernel_call_lines(tree: ast.AST) -> list[int]:
    """Find every Call node whose func is a bare `Name("Kernel")`.

    Catches both `Kernel(...)` and `Kernel(settings=..., ...)`. Does
    NOT catch `cora.infrastructure.kernel.Kernel(...)` — but that
    namespaced form does not appear in tests today, and adding it
    would still be caught by the import linter in tach.toml.
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
@pytest.mark.parametrize("test_file", _integration_test_files(), ids=_qualified)
def test_no_direct_kernel_construction_in_integration_test(test_file: Path) -> None:
    qualified = _qualified(test_file)
    tree = ast.parse(test_file.read_text(), filename=str(test_file))
    lines = _kernel_call_lines(tree)
    assert not lines, (
        f"{qualified}: direct Kernel(...) construction at line(s) "
        f"{sorted(lines)}. Integration tests must use "
        f"`build_postgres_deps(db_pool, ...)` from "
        f"`tests.integration._helpers` so the wiring stays in lockstep "
        f"with production. Add a new factory parameter if you need a "
        f"shape the helper does not yet support."
    )


@pytest.mark.architecture
def test_integration_test_files_were_actually_discovered() -> None:
    """Drift catcher: if the integration glob breaks, fail loudly."""
    files = _integration_test_files()
    assert len(files) >= 50, (
        f"Expected >=50 integration test files, found {len(files)}. "
        f"The integration suite shouldn't shrink dramatically; check "
        f"the glob in {Path(__file__).name}."
    )
