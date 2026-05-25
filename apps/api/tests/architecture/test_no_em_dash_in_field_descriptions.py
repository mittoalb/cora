"""Wire-visible Pydantic + Enum prose must not contain em dashes.

The CLAUDE.md hard rule is "no em dashes in user-facing prose; use
commas, colons, or rephrase". Three surfaces are user-facing because
they reach external clients verbatim through the OpenAPI schema and
MCP `tools/list`:

  1. `description=` arguments on `Field(...)` and `mcp.tool(...)`.
  2. Docstrings on `BaseModel` subclasses (rendered as `description`
     on the JSON schema's `$defs` entry for the model).
  3. Docstrings on `Enum` / `StrEnum` subclasses (rendered the same
     way for enums referenced from schemas).

Per-enum-member literal docstrings (the bare-string-after-assignment
pattern) are also scanned because Pydantic-emitted JSON Schema can
surface them in tooling that walks the AST (for example, the
`get_family` MCP tool surfaces `Affordance` member descriptions).

Internal docstrings + `#` comments stay out of scope; the boundary
the test pins is the wire-visible surface.
"""

import ast
import re
from pathlib import Path

import pytest

from tests.architecture.conftest import tracked_python_files

_EM_DASH = "—"

_DESCRIPTION_BLOCK = re.compile(
    r"description\s*=\s*(\(([^()]*(?:\([^()]*\)[^()]*)*)\)|\"[^\"]*\")",
    re.DOTALL,
)


def _description_violations(text: str) -> list[int]:
    return [
        text[: m.start()].count("\n") + 1
        for m in _DESCRIPTION_BLOCK.finditer(text)
        if _EM_DASH in m.group(1)
    ]


_WIRE_BASES = {"BaseModel", "Enum", "StrEnum", "IntEnum"}


def _class_is_wire_visible(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id in _WIRE_BASES:
            return True
        if isinstance(base, ast.Attribute) and base.attr in _WIRE_BASES:
            return True
    return False


def _class_docstring_violations(text: str) -> list[tuple[int, str]]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or not _class_is_wire_visible(node):
            continue
        docstring = ast.get_docstring(node)
        if docstring and _EM_DASH in docstring:
            out.append((node.lineno, node.name))
        prev_was_assign = False
        for stmt in node.body:
            if isinstance(stmt, ast.Assign | ast.AnnAssign):
                prev_was_assign = True
                continue
            if (
                prev_was_assign
                and isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
                and _EM_DASH in stmt.value.value
            ):
                out.append((stmt.lineno, f"{node.name} member docstring"))
            prev_was_assign = False
    return out


@pytest.mark.parametrize(
    "path",
    sorted(p for p in tracked_python_files() if p.suffix == ".py"),
    ids=lambda p: str(p.relative_to(p.parents[3])),
)
def test_no_em_dash_in_wire_visible_prose(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if _EM_DASH not in text:
        return
    field_violations = _description_violations(text) if "description" in text else []
    class_violations = _class_docstring_violations(text)
    if not field_violations and not class_violations:
        return
    parts: list[str] = []
    if field_violations:
        parts.append(
            f"Field(description=...) lines {field_violations}",
        )
    if class_violations:
        rendered = ", ".join(f"{ln}:{label}" for ln, label in class_violations)
        parts.append(f"wire-visible class docstrings [{rendered}]")
    detail = "; ".join(parts)
    msg = (
        f"{path}: em dash (U+2014) found in {detail}. Use commas, "
        f"colons, or rephrase per CLAUDE.md hard rules."
    )
    raise AssertionError(msg)
