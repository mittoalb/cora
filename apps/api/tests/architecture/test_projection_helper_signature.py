"""Pin: no projection helper takes `pool: asyncpg.Pool | None`.

Projection query helpers under `cora/*/projections/*.py` historically
accepted `pool: asyncpg.Pool | None` and short-circuited with a benign
default when pool was None. The branch existed for test ergonomics but
was dead in practice: tests that opt out of Postgres bypass the handler
path entirely and exercise the pure decider directly. The five
equipment-side helpers were tightened to require a non-None pool;
the permissive short-circuit moved out of each helper and into the
calling handler, where it is explicit.

This fitness function keeps the tightening sticky: any new projection
helper added under any BC's `projections/` package must accept a
non-None `pool: asyncpg.Pool`. If a future helper genuinely needs to
tolerate a missing pool, surface that decision at the caller, not in
the helper signature.

Scope: only `cora/*/projections/*.py`. Cross-BC read helpers under
`cora/*/aggregates/*/read.py` are not (yet) covered; promote here if
that scope earns a follow-up sweep.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files


def _projection_helper_files() -> list[Path]:
    """Tracked `.py` files under `cora/*/projections/`, excluding __init__.py."""
    return sorted(
        path
        for path in tracked_python_files()
        if "/projections/" in str(path) and path.name != "__init__.py"
    )


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _annotation_text(annotation: ast.expr | None) -> str:
    """Render a parameter annotation as flat text for substring matching.

    `ast.unparse` reproduces the source-level annotation (`asyncpg.Pool | None`
    -> `'asyncpg.Pool | None'`), which is exactly the shape we want to ban.
    """
    if annotation is None:
        return ""
    return ast.unparse(annotation)


def _async_pool_or_none_offenders(tree: ast.AST) -> list[tuple[str, str]]:
    """Return (function_name, parameter_annotation) for every async def
    function whose `pool` parameter is annotated as `asyncpg.Pool | None`
    (or any of the equivalent forms: `Optional[asyncpg.Pool]`,
    `None | asyncpg.Pool`)."""
    out: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        for arg in node.args.args:
            if arg.arg != "pool":
                continue
            text = _annotation_text(arg.annotation)
            # Banned shapes: `asyncpg.Pool | None`, `None | asyncpg.Pool`,
            # `Optional[asyncpg.Pool]`, `Pool | None`, `None | Pool`.
            normalized = text.replace(" ", "")
            if (
                "asyncpg.Pool|None" in normalized
                or "None|asyncpg.Pool" in normalized
                or "Optional[asyncpg.Pool]" in normalized
                or normalized in {"Pool|None", "None|Pool", "Optional[Pool]"}
            ):
                out.append((node.name, text))
    return out


@pytest.mark.architecture
@pytest.mark.parametrize("path", _projection_helper_files(), ids=_qualified)
def test_projection_helper_pool_param_is_non_none(path: Path) -> None:
    """Projection helpers must take pool: asyncpg.Pool (not Pool | None)."""
    tree = ast.parse(path.read_text())
    offenders = _async_pool_or_none_offenders(tree)
    assert not offenders, (
        f"{_qualified(path)} declares projection helper(s) with a nullable "
        "pool parameter:\n  "
        + "\n  ".join(f"async def {name}(..., pool: {annot})" for name, annot in offenders)
        + "\n\nTighten the signature to `pool: asyncpg.Pool` and move any "
        "pool-None short-circuit to the calling handler. The five "
        "equipment-side helpers (load_asset_lifecycle, load_asset_location, "
        "load_active_mount_children, load_active_frame_consumers, "
        "load_mount_id_by_slot_code) are the canonical reference."
    )
