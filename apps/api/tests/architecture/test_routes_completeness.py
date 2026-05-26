"""Every domain Error class is registered as an HTTP exception handler.

Adding a new error to `cora/<bc>/aggregates/.../state.py` and
forgetting to wire it into `cora/<bc>/routes.py::register_<bc>_routes`
surfaces in production as an unmapped 500 instead of a clean
4xx. This test makes that drift impossible.

The test inspects each BC's `routes.py` source for class-name
mentions inside `add_exception_handler` calls. Coarser than
walking the AST of `register_<bc>_routes` directly, but robust
to the existing tuple-loop pattern and easy to read.

WIP_ERRORS is an explicit per-BC allowlist for errors whose
slice is mid-flight. Each entry SHOULD cite the phase that closes
it; reviewers should reject additions without a phase reference.
"""

from __future__ import annotations

import importlib
import inspect
from typing import Any

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files

# Errors not yet registered because their slice is in flight,
# OR pre-existing drift this test surfaced and which is being
# cleaned up in a follow-up. Each entry MUST have a comment.
# Empty each entry as the slice ships / drift is fixed.
WIP_ERRORS: dict[str, frozenset[str]] = {}


def _bc_module(bc: str) -> Any:
    return importlib.import_module(f"cora.{bc}")


def _bc_error_classes(bc: str) -> set[str]:
    """Every Error class re-exported on the BC's public surface or its aggregates."""
    pkg = _bc_module(bc)
    out: set[str] = set()
    for name in getattr(pkg, "__all__", []):
        if not name.endswith("Error"):
            continue
        cls = getattr(pkg, name, None)
        if isinstance(cls, type) and issubclass(cls, Exception):
            out.add(name)
    # Also include aggregate-level errors (the canonical home).
    aggs_pkg_name = f"cora.{bc}.aggregates"
    try:
        aggs = importlib.import_module(aggs_pkg_name)
    except ModuleNotFoundError:
        return out
    for agg_name in getattr(aggs, "__all__", []):
        agg = getattr(aggs, agg_name, None)
        if not inspect.ismodule(agg):
            continue
        for n in getattr(agg, "__all__", []):
            cls = getattr(agg, n, None)
            if isinstance(cls, type) and issubclass(cls, Exception) and n.endswith("Error"):
                out.add(n)
    # Walk known sub-aggregates too (for example trust.aggregates.conduit).
    # Enumeration is git-aware: pre-commit doesn't stash untracked files,
    # so a filesystem scan would see half-staged WIP aggregates and
    # false-fail. See conftest module docstring for the rationale.
    aggs_dir = CORA_ROOT / bc / "aggregates"
    sub_dirs = {f.parent for f in tracked_python_files() if f.parent.parent == aggs_dir}
    for sub_dir in sub_dirs:
        sub_pkg_name = f"{aggs_pkg_name}.{sub_dir.name}"
        try:
            sub_pkg = importlib.import_module(sub_pkg_name)
        except (ModuleNotFoundError, ImportError):
            continue
        for n in getattr(sub_pkg, "__all__", []):
            cls = getattr(sub_pkg, n, None)
            if isinstance(cls, type) and issubclass(cls, Exception) and n.endswith("Error"):
                out.add(n)
    return out


def _routes_source(bc: str) -> str:
    routes = importlib.import_module(f"cora.{bc}.routes")
    return inspect.getsource(routes)


@pytest.mark.architecture
@pytest.mark.parametrize("bc", BCS)
def test_every_domain_error_registered_as_http_handler(bc: str) -> None:
    error_classes = _bc_error_classes(bc)
    if not error_classes:
        pytest.skip(f"{bc}: no Error classes on the public surface")

    src = _routes_source(bc)
    wip = WIP_ERRORS.get(bc, frozenset())
    unregistered = {name for name in error_classes if name not in src and name not in wip}
    assert not unregistered, (
        f"{bc}: domain errors not registered as HTTP exception handlers: "
        f"{sorted(unregistered)}\n"
        f"Add them to a tuple loop in cora/{bc}/routes.py::register_{bc}_routes."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("bc", BCS)
def test_wip_errors_actually_exist(bc: str) -> None:
    """WIP_ERRORS entries must point at real Error classes. Drift catcher."""
    wip = WIP_ERRORS.get(bc, frozenset())
    if not wip:
        pytest.skip(f"{bc}: no WIP errors")
    real = _bc_error_classes(bc)
    stale = wip - real
    assert not stale, (
        f"{bc}: WIP_ERRORS entries no longer exist as Error classes: {sorted(stale)}; remove them."
    )
