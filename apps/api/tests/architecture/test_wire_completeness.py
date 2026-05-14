"""Every shipped slice is wired into its BC's wire_<bc> function.

A slice with `handler.py` is considered "shipped" and must be
referenced by `cora/<bc>/wire.py::wire_<bc>` (so it ends up in
the BC's handler bundle and reachable from routes / tools).

A slice without `handler.py` is treated as a stub (in flight)
and skipped, mirroring `test_slice_contract.py`.

This guards against the "I added the slice but forgot to bind
it in wire.py" failure mode, which today only surfaces when a
contract test happens to hit the unbound endpoint.
"""

import importlib
import inspect

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT


def _shipped_slices_per_bc() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for bc in BCS:
        features = CORA_ROOT / bc / "features"
        if not features.is_dir():
            continue
        for slice_dir in sorted(features.iterdir()):
            if not slice_dir.is_dir() or slice_dir.name.startswith("_"):
                continue
            if not (slice_dir / "handler.py").is_file():
                continue
            out.append((bc, slice_dir.name))
    return out


@pytest.mark.architecture
@pytest.mark.parametrize(("bc", "slice_name"), _shipped_slices_per_bc())
def test_slice_is_wired_into_bc(bc: str, slice_name: str) -> None:
    wire_module = importlib.import_module(f"cora.{bc}.wire")
    wire_fn = getattr(wire_module, f"wire_{bc}", None)
    assert wire_fn is not None, f"cora.{bc}.wire.wire_{bc} not found"
    src = inspect.getsource(wire_fn)
    needle = f"{slice_name}.bind"
    assert needle in src, (
        f"cora.{bc}.features.{slice_name} has handler.py but is not bound in "
        f"wire_{bc} (looking for `{needle}`). Add it to the handler bundle."
    )


@pytest.mark.architecture
@pytest.mark.parametrize("bc", BCS)
def test_wire_function_exists(bc: str) -> None:
    """Each BC must expose `wire_<bc>(deps)` from its wire module."""
    wire_module = importlib.import_module(f"cora.{bc}.wire")
    wire_fn = getattr(wire_module, f"wire_{bc}", None)
    assert callable(wire_fn), f"cora.{bc}.wire.wire_{bc} must be callable"
