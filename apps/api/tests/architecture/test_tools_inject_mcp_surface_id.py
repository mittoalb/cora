"""Every BC MCP tool MUST call `get_mcp_surface_id()` at the handler call.

Every `features/<slice>/tool.py` passes
`surface_id=get_mcp_surface_id()` to the inner handler call site.
This test pins that invariant against future drift: a new MCP tool
landing without `get_mcp_surface_id()`
would either pass the nil sentinel (bypassing V2 per-surface policy
enforcement on MCP-arrived calls) OR raise at runtime since the
handler Protocol now requires the kwarg in shape.

Asymmetric vs HTTP routes: MCP tools call `get_mcp_surface_id()`
directly (no `Depends` in FastMCP). The asymmetry is deliberate
and documented at `cora.infrastructure.routing.get_mcp_surface_id`
— FastMCP doesn't surface a `Request`-shaped object cleanly, and the
design lock forbids client-asserted surface in either transport.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files


def _tool_files() -> list[Path]:
    tracked = tracked_python_files()
    out: list[Path] = []
    for path in sorted(tracked):
        rel = path.relative_to(CORA_ROOT) if path.is_relative_to(CORA_ROOT) else None
        if rel is None:
            continue
        parts = rel.parts
        if len(parts) == 4 and parts[0] in BCS and parts[1] == "features" and parts[3] == "tool.py":
            out.append(path)
    return out


def _qualified(tool_file: Path) -> str:
    rel = tool_file.relative_to(CORA_ROOT)
    return "cora." + ".".join(rel.with_suffix("").parts)


def _imports_get_mcp_surface_id(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "get_mcp_surface_id":
                    return True
    return False


def _calls_get_mcp_surface_id(tree: ast.AST) -> bool:
    """Walk for `get_mcp_surface_id()` invocation anywhere in the file."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "get_mcp_surface_id":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "get_mcp_surface_id":
            return True
    return False


@pytest.mark.architecture
@pytest.mark.parametrize("tool_file", _tool_files(), ids=_qualified)
def test_tool_calls_get_mcp_surface_id(tool_file: Path) -> None:
    qualified = _qualified(tool_file)
    source = tool_file.read_text()
    tree = ast.parse(source, filename=str(tool_file))

    if not _imports_get_mcp_surface_id(tree):
        pytest.fail(
            f"{qualified} does not import `get_mcp_surface_id` from "
            f"cora.infrastructure.routing. Every MCP tool must resolve "
            f"the arrival Surface server-side per the design lock."
        )

    assert _calls_get_mcp_surface_id(tree), (
        f"{qualified} imports get_mcp_surface_id but never invokes it. "
        f"Pass it into the inner handler call: "
        f"`await handler(..., surface_id=get_mcp_surface_id())`."
    )


@pytest.mark.architecture
def test_tool_files_were_actually_discovered() -> None:
    """Drift catcher."""
    files = _tool_files()
    assert len(files) >= 100, (
        f"Expected at least 100 tool files across the 15 BCs, found "
        f"{len(files)}. The discovery glob may be wrong."
    )
