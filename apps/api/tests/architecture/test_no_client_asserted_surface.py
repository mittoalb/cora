"""AH1 enforcement: no route/tool may declare a client-asserted Surface.

Phase B Iter C-2 design lock AH1 forbids the arrival Surface from
being client-driven. `surface_id` MUST be resolved server-side by
`get_surface_id` (HTTP) / `get_mcp_surface_id` (MCP), never read off
a Header / Query / path-param / MCP tool argument the client controls.

This test walks every `features/*/route.py` and `features/*/tool.py`
for AST patterns that would let a client assert the surface:

  - `Header(alias="X-Surface-Id")` / `Header(alias="x-surface-id")`
    etc. on a route — anything where Header's alias keyword contains
    the substring "surface" (case-insensitive)
  - `Query(...)` parameter whose surrounding variable name OR alias
    contains "surface"
  - MCP tool function parameters whose name contains "surface" that
    aren't explicitly the typed UUID resolved server-side

The check is conservative: variables literally named `surface_id`
in routes are ALLOWED only when bound via `Depends(get_surface_id)`
(verified by sibling fitness `test_routes_inject_surface_id.py`).
Here we explicitly fail on the client-asserted shapes.

## Exception: `target_surface_id` path param on the get_surface route

`apps/api/src/cora/trust/features/get_surface/route.py` declares
`target_surface_id` as a Path parameter (it identifies the Surface
record to fetch). That's a resource identifier in the URL, not the
arrival Surface — distinct concept, distinct name, no AH1 violation.
The substring check uses `surface_id` (with underscore) so the
`target_` prefix is enough; `surface` alone would false-match.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files

_FASTAPI_CLIENT_PARAM_FACTORIES = frozenset({"Header", "Query", "Cookie", "Form", "File", "Body"})


def _route_and_tool_files() -> list[Path]:
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
            and parts[3] in ("route.py", "tool.py")
        ):
            out.append(path)
    return out


def _qualified(file: Path) -> str:
    rel = file.relative_to(CORA_ROOT)
    return "cora." + ".".join(rel.with_suffix("").parts)


def _is_client_asserted_surface_call(node: ast.Call) -> str | None:
    """Return a description if this Call is a FastAPI parameter factory
    (Header/Query/Cookie/Form/File/Body) whose alias kwarg references
    'surface'; otherwise None."""
    func = node.func
    factory = None
    if isinstance(func, ast.Name) and func.id in _FASTAPI_CLIENT_PARAM_FACTORIES:
        factory = func.id
    elif isinstance(func, ast.Attribute) and func.attr in _FASTAPI_CLIENT_PARAM_FACTORIES:
        factory = func.attr
    if factory is None:
        return None
    for kw in node.keywords:
        if kw.arg == "alias" and isinstance(kw.value, ast.Constant):
            alias = str(kw.value.value).lower()
            if "surface" in alias:
                return f"{factory}(alias={kw.value.value!r})"
    return None


@pytest.mark.architecture
@pytest.mark.parametrize("file", _route_and_tool_files(), ids=_qualified)
def test_no_header_or_query_asserts_surface(file: Path) -> None:
    """No FastAPI parameter factory (Header/Query/Cookie/Form/File/Body)
    may have an alias that references the Surface. Clients must never
    be able to inject which Surface their request arrived on (AH1)."""
    qualified = _qualified(file)
    source = file.read_text()
    tree = ast.parse(source, filename=str(file))

    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        descr = _is_client_asserted_surface_call(node)
        if descr is not None:
            offenders.append(f"{descr} at line {node.lineno}")

    assert not offenders, (
        f"{qualified}: client-asserted surface detected: "
        f"{', '.join(offenders)}. AH1 forbids the arrival Surface from "
        f"being client-controlled. Use `Depends(get_surface_id)` (HTTP) "
        f"or `get_mcp_surface_id()` (MCP) at the call site instead."
    )


@pytest.mark.architecture
def test_route_tool_files_were_actually_discovered() -> None:
    files = _route_and_tool_files()
    assert len(files) >= 200, (
        f"Expected at least 200 route+tool files across the 15 BCs, "
        f"found {len(files)}. The discovery glob may be wrong."
    )
