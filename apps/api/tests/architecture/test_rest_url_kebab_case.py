"""REST URL path segments use kebab-case.

Per the convention at `docs/reference/conventions.md#rest-url-paths`,
hyphens (not underscores) separate words inside literal URL path
segments. Path parameters in `{snake_case}` placeholders are
exempt because FastAPI binds them to Python function arguments
which follow PEP 8.

The test walks every `route.py` under `src/cora/<bc>/features/`,
extracts the path strings from `@router.<verb>(...)` decorators,
strips out the `{...}` placeholders, and asserts no remaining
literal segment contains an underscore between letters.

Violators surface here rather than in a contract test because
this is a vocabulary rule, not behavior. The fix is always
"replace underscore with hyphen in the URL string." Python
identifiers (handler function name, slice directory, command
class) are NOT affected.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

_PLACEHOLDER = re.compile(r"\{[^}]+\}")
_SNAKE_SEGMENT = re.compile(r"/[a-z]+_[a-z]+")


def _route_files() -> list[Path]:
    return sorted(
        p
        for p in tracked_python_files()
        if p.name == "route.py" and "features" in p.parts and p.is_relative_to(CORA_ROOT)
    )


def _extract_router_paths(source: str) -> list[str]:
    """Return every literal URL string passed to a @router.<verb>(...) decorator."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    paths: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue
        value = func.value
        if not (isinstance(value, ast.Name) and value.id == "router"):
            continue
        if func.attr not in {"get", "post", "put", "patch", "delete"}:
            continue
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                paths.append(arg.value)
                break
    return paths


def _snake_segments(path: str) -> list[str]:
    """Return the literal `/snake_case` segments in a URL path, ignoring placeholders."""
    cleaned = _PLACEHOLDER.sub("/PARAM", path)
    return _SNAKE_SEGMENT.findall(cleaned)


@pytest.mark.architecture
def test_rest_url_path_segments_are_kebab_case() -> None:
    violations: list[tuple[Path, str, list[str]]] = []
    for route_file in _route_files():
        source = route_file.read_text(encoding="utf-8")
        for url in _extract_router_paths(source):
            bad = _snake_segments(url)
            if bad:
                violations.append((route_file, url, bad))

    if not violations:
        return

    api_root = CORA_ROOT.parent.parent
    lines = [
        f"Found {len(violations)} REST URL path(s) with snake_case literal segments.",
        "URL path segments use kebab-case per docs/reference/conventions.md#rest-url-paths.",
        "Replace underscores with hyphens in the URL string. Python handler",
        "function names, slice directories, and command classes are unaffected.",
        "",
    ]
    for path, url, bad in violations[:20]:
        lines.append(f"  {path.relative_to(api_root)}: {url}  (snake segments: {bad})")
    if len(violations) > 20:
        lines.append(f"  ... and {len(violations) - 20} more")
    pytest.fail("\n".join(lines))
