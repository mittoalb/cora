"""Every BC HTTP route MUST inject the arrival Surface via FastAPI Depends.

Phase B Iter C-2c enforcement. The Iter C-2b sweep added
`surface_id: Annotated[UUID, Depends(get_surface_id)]` to every
`features/<slice>/route.py` so the inbound request's process-pinned
Surface (HTTP) reaches the handler. This test pins that invariant
against future drift: a new route landing without `Depends(get_surface_id)`
would either fail at runtime when calling the surface_id-requiring
handler signature, OR silently pass the nil sentinel — bypassing
V2 per-surface policy enforcement (forthcoming) on that endpoint.

The test parametrizes over every git-tracked `features/<slice>/route.py`
and asserts the file imports `get_surface_id` and references it
inside a `Depends(...)` call. AST walk (not a substring match) to
avoid false positives from comments / docstrings.

## Why import-AND-Depends, not just import

A future drift could keep the import (someone removed the Depends
but left the import) — the assertion on the call site is what
matters; the import check is a faster pre-filter that produces a
better error message when the import is the actual omission.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files


def _route_files() -> list[Path]:
    tracked = tracked_python_files()
    out: list[Path] = []
    for path in sorted(tracked):
        rel = path.relative_to(CORA_ROOT) if path.is_relative_to(CORA_ROOT) else None
        if rel is None:
            continue
        parts = rel.parts
        if (
            len(parts) == 4
            and parts[0] in BCS
            and parts[1] == "features"
            and parts[3] == "route.py"
        ):
            out.append(path)
    return out


def _qualified(route_file: Path) -> str:
    rel = route_file.relative_to(CORA_ROOT)
    return "cora." + ".".join(rel.with_suffix("").parts)


def _imports_get_surface_id(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "get_surface_id":
                    return True
    return False


def _has_depends_on_get_surface_id(tree: ast.AST) -> bool:
    """Walk for a Depends(get_surface_id) Call node anywhere in the
    file. Conservative: matches either bare `Depends(get_surface_id)`
    or `<ns>.Depends(get_surface_id)`."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_depends = (isinstance(func, ast.Name) and func.id == "Depends") or (
            isinstance(func, ast.Attribute) and func.attr == "Depends"
        )
        if not is_depends or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Name) and first.id == "get_surface_id":
            return True
        if isinstance(first, ast.Attribute) and first.attr == "get_surface_id":
            return True
    return False


@pytest.mark.architecture
@pytest.mark.parametrize("route_file", _route_files(), ids=_qualified)
def test_route_injects_get_surface_id(route_file: Path) -> None:
    qualified = _qualified(route_file)
    source = route_file.read_text()
    tree = ast.parse(source, filename=str(route_file))

    if not _imports_get_surface_id(tree):
        pytest.fail(
            f"{qualified} does not import `get_surface_id` from "
            f"cora.infrastructure.routing. Every HTTP route must inject "
            f"the arrival Surface via Depends(get_surface_id) per Phase B "
            f"Iter C-2 AH1 (process-derived, never client-asserted)."
        )

    assert _has_depends_on_get_surface_id(tree), (
        f"{qualified} imports get_surface_id but no "
        f"`Depends(get_surface_id)` call site found. Wire it as a route "
        f"parameter: `surface_id: Annotated[UUID, Depends(get_surface_id)]` "
        f"and thread it into the handler call."
    )


@pytest.mark.architecture
def test_route_files_were_actually_discovered() -> None:
    """Drift catcher."""
    files = _route_files()
    assert len(files) >= 100, (
        f"Expected at least 100 route files across the 15 BCs, found "
        f"{len(files)}. The discovery glob may be wrong."
    )
