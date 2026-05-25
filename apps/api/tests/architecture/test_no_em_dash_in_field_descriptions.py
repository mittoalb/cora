"""Pydantic Field `description=` strings must not contain em dashes.

Field descriptions surface in the OpenAPI schema and in MCP tool
schemas (i.e. they reach external clients verbatim). CORA's
convention is "no em dashes in user-facing prose; use commas,
colons, or rephrase" (see CLAUDE.md hard rules). Internal
docstrings + comments are out of scope for this fitness; the
boundary the test pins is the wire-visible description.

Matches `description=` followed by either a single string literal
or a parenthesized concatenation of string literals, and rejects
any em dash (`U+2014`) inside the literal value. Other Unicode
characters (arrows, section signs, etc.) are not flagged.
"""

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


@pytest.mark.parametrize(
    "path",
    sorted(p for p in tracked_python_files() if p.suffix == ".py"),
    ids=lambda p: str(p.relative_to(p.parents[3])),
)
def test_no_em_dash_in_field_descriptions(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "description" not in text or _EM_DASH not in text:
        return
    violations = _description_violations(text)
    assert not violations, (
        f"{path}: em dash (U+2014) found inside Field description on "
        f"lines {violations}. Use commas, colons, or rephrase per "
        f"CLAUDE.md hard rules."
    )
