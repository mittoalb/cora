"""Command-slice route files don't raise ``HTTPException`` directly.

Per ``docs/reference/patterns.md`` Rejections:

  > Routes do NOT wrap handler calls in try/except. Decider raises,
  > central handler catches, FastAPI emits the JSON response. The
  > response body is uniform: {"detail": str(exc)}.

This rule applies to **command** slices. Query slices are scoped out:
patterns.md Query slices explicitly documents
``route.py  # GET /<resource>/{id} -> 200 + DTO  (404 on None)``,
i.e. the route maps the ``Aggregate | None`` return from fold-on-read
to either a 200 + DTO or a 404 inline. ``get_*`` and ``list_*`` slices
do this 20+ times today; that's the convention, not drift.

Note on the 2026-05-22 audit's D4 finding: the audit flagged Trust's
``get_surface/route.py`` for inline ``HTTPException(404)``, but
``get_surface`` is a query slice and the inline 404 is the documented
pattern (parallel to every other ``get_*`` route). No violation; the
Phase ζ allowlist drops the D4 entry.

For command slices, ``GRANDFATHERED_COMMAND_ROUTES`` is the explicit
work-tracker for documented inline raises (e.g. the
capability-dependent-handler 503 pattern when an external dependency
isn't wired).
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


# Command-slice route files with a documented inline raise.
GRANDFATHERED_COMMAND_ROUTES: frozenset[str] = frozenset(
    {
        # Capability-dependent-handler 503: re_debrief_run is unwired
        # when ANTHROPIC_API_KEY isn't configured (handler: ... | None).
        # The route guards on None and raises 503 inline. Documented at
        # agent/wire.py and agent/tools.py.
        "cora.agent.features.re_debrief_run.route",
    }
)


def _command_route_files() -> list[Path]:
    """Tracked route.py files in command slices (those with a sibling decider.py)."""
    tracked = tracked_python_files()
    out: list[Path] = []
    for bc in BCS:
        features = CORA_ROOT / bc / "features"
        for f in tracked:
            if (
                f.name == "route.py"
                and f.parent.parent == features
                and not f.parent.name.startswith("_")
                and (f.parent / "decider.py") in tracked
            ):
                out.append(f)
    return sorted(out)


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _inline_http_exception_lines(tree: ast.Module) -> list[int]:
    """Lines of ``raise HTTPException(...)`` statements."""
    out: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        exc = node.exc
        # `raise HTTPException(...)`
        if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
            if exc.func.id == "HTTPException":
                out.append(node.lineno)
        # `raise fastapi.HTTPException(...)`
        elif (
            isinstance(exc, ast.Call)
            and isinstance(exc.func, ast.Attribute)
            and exc.func.attr == "HTTPException"
        ):
            out.append(node.lineno)
    return out


@pytest.mark.architecture
@pytest.mark.parametrize("route_file", _command_route_files(), ids=_qualified)
def test_command_route_does_not_raise_http_exception(route_file: Path) -> None:
    qualified = _qualified(route_file)
    if qualified in GRANDFATHERED_COMMAND_ROUTES:
        pytest.skip(f"{qualified} is in GRANDFATHERED_COMMAND_ROUTES")
    tree = ast.parse(route_file.read_text())
    lines = _inline_http_exception_lines(tree)
    assert not lines, (
        f"{qualified} raises HTTPException directly at "
        f"line(s) {lines}. Per docs/reference/patterns.md, command-slice "
        "routes don't wrap handlers; raise a typed domain error and "
        "register it on the BC's central exception handler instead."
    )


@pytest.mark.architecture
def test_grandfathered_routes_actually_raise_http_exception() -> None:
    """``GRANDFATHERED_COMMAND_ROUTES`` entries must still contain an inline raise."""
    for qualified in GRANDFATHERED_COMMAND_ROUTES:
        parts = qualified.split(".")
        assert parts[0] == "cora", f"{qualified}: must start with 'cora.'"
        path = CORA_ROOT.joinpath(*parts[1:]).with_suffix(".py")
        assert path.is_file(), f"{qualified}: file no longer exists; remove allowlist"
        tree = ast.parse(path.read_text())
        lines = _inline_http_exception_lines(tree)
        assert lines, (
            f"{qualified}: no longer raises HTTPException; remove "
            "GRANDFATHERED_COMMAND_ROUTES entry"
        )
