"""Deciders must be pure: no I/O, no clock, no random, no IDs.

Per CORA's "non-determinism in deciders, period" principle: every
non-deterministic value (clock, IDs, random, HTTP, FS) is injected
via port from the handler and captured in the event payload.
Deciders receive `now` and `new_id` as parameters; they MUST NOT
call `datetime.now()`, `uuid4()`, `asyncio.sleep`, or import any
I/O library directly.

This test scans every `<bc>/features/<slice>/decider.py` with AST
and rejects forbidden calls and imports.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files

_FORBIDDEN_TOP_LEVEL_IMPORTS: frozenset[str] = frozenset(
    {
        "asyncpg",
        "httpx",
        "requests",
        "urllib",
        "anthropic",
        "openai",
        "boto3",
        "psycopg",
        "psycopg2",
        "redis",
        "kafka",
        "asyncio",  # deciders are sync
        "subprocess",
        "socket",
        "tempfile",
        "shutil",
        "os",  # filesystem; deciders should not touch it
    }
)

# (object_name, attribute) pairs banned in deciders.
_FORBIDDEN_ATTR_CALLS: frozenset[tuple[str, str]] = frozenset(
    {
        ("datetime", "now"),
        ("datetime", "utcnow"),
        ("datetime", "today"),
        ("uuid", "uuid1"),
        ("uuid", "uuid3"),
        ("uuid", "uuid4"),
        ("uuid", "uuid5"),
        ("uuid", "uuid6"),
        ("uuid", "uuid7"),
        ("uuid", "uuid8"),
        ("uuid_utils", "uuid7"),
        ("time", "time"),
        ("time", "monotonic"),
        ("time", "sleep"),
        ("random", "random"),
        ("random", "randint"),
        ("random", "choice"),
        ("os", "getenv"),
        ("os", "environ"),
        ("Path", "read_text"),
        ("Path", "write_text"),
    }
)

# Bare function names banned in deciders (for example `uuid4()` after
# `from uuid import uuid4`). Not exhaustive; catches the common shapes.
_FORBIDDEN_BARE_CALLS: frozenset[str] = frozenset(
    {
        "uuid1",
        "uuid3",
        "uuid4",
        "uuid5",
        "uuid6",
        "uuid7",
        "uuid8",
        "open",
        "input",
        "getenv",
    }
)


def _decider_files() -> list[Path]:
    tracked = tracked_python_files()
    out: list[Path] = []
    for bc in BCS:
        features = CORA_ROOT / bc / "features"
        out.extend(
            sorted(
                f
                for f in tracked
                if f.name == "decider.py"
                and f.parent.parent == features
                and not f.parent.name.startswith("_")
            )
        )
    return out


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


@pytest.mark.architecture
@pytest.mark.parametrize("decider", _decider_files(), ids=_qualified)
def test_decider_is_pure(decider: Path) -> None:
    """Decider files contain no I/O, no clock, no random, no ID generation."""
    tree = ast.parse(decider.read_text())
    qualified = _qualified(decider)
    violations: list[str] = []

    for node in ast.walk(tree):
        # `import asyncpg` / `from asyncpg import ...`
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in _FORBIDDEN_TOP_LEVEL_IMPORTS:
                    violations.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top in _FORBIDDEN_TOP_LEVEL_IMPORTS:
                violations.append(f"line {node.lineno}: from {node.module} import ...")

        # `datetime.now()`, `uuid.uuid4()`, etc.
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                pair = (func.value.id, func.attr)
                if pair in _FORBIDDEN_ATTR_CALLS:
                    violations.append(f"line {node.lineno}: {pair[0]}.{pair[1]}()")
            elif isinstance(func, ast.Name) and func.id in _FORBIDDEN_BARE_CALLS:
                violations.append(f"line {node.lineno}: {func.id}()")

    assert not violations, (
        f"{qualified} violates decider purity:\n  " + "\n  ".join(violations) + "\n"
        "Inject `now: datetime` / `new_id: UUID` via the handler instead."
    )
