"""Every shipped slice is registered in its BC's `routes.py` and `tools.py`.

A slice with `handler.py` is considered "shipped" (mirrors
`test_wire_completeness.py`) and must therefore appear on all three
composition surfaces of its BC:

  - `cora/<bc>/wire.py::wire_<bc>` — bound into `<BC>Handlers`
    (covered by `test_wire_completeness.py`)
  - `cora/<bc>/routes.py::register_<bc>_routes` — `<slice>.router`
    included on the FastAPI app (covered here)
  - `cora/<bc>/tools.py::register_<bc>_tools` — `<slice>_tool.register(...)`
    invoked on the FastMCP server (covered here)

This guards against the "I wired the handler but only exposed it
on REST" / "only on MCP" failure mode. Today REST and MCP have
parity across every BC; this test locks that in.

Scope note: a slice without `handler.py` is treated as a stub (in
flight) and skipped. The `_tool.register` needle matches the
imported alias pattern used in every BC's `tools.py`
(`from cora.<bc>.features.<slice> import tool as <slice>_tool`),
so conditional dereferences such as Agent's `regenerate_run_debrief`
(which goes through `_resolve_regenerate_run_debrief` rather than a
direct `get_handlers().regenerate_run_debrief` access) are still
detected via the preceding `regenerate_run_debrief_tool.register(...)`
call.
"""

import importlib
import inspect

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files


def _shipped_slices_per_bc() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    tracked = tracked_python_files()
    for bc in BCS:
        features = CORA_ROOT / bc / "features"
        handlers = sorted(
            f
            for f in tracked
            if f.name == "handler.py"
            and f.parent.parent == features
            and not f.parent.name.startswith("_")
        )
        for handler in handlers:
            out.append((bc, handler.parent.name))
    return out


@pytest.mark.architecture
@pytest.mark.parametrize("bc", BCS)
def test_register_routes_function_exists(bc: str) -> None:
    """Each BC must expose `register_<bc>_routes(app)` from its routes module."""
    routes_module = importlib.import_module(f"cora.{bc}.routes")
    register_fn = getattr(routes_module, f"register_{bc}_routes", None)
    assert callable(register_fn), f"cora.{bc}.routes.register_{bc}_routes must be callable"


@pytest.mark.architecture
@pytest.mark.parametrize("bc", BCS)
def test_register_tools_function_exists(bc: str) -> None:
    """Each BC must expose `register_<bc>_tools(mcp, *, get_handlers)` from its tools module."""
    tools_module = importlib.import_module(f"cora.{bc}.tools")
    register_fn = getattr(tools_module, f"register_{bc}_tools", None)
    assert callable(register_fn), f"cora.{bc}.tools.register_{bc}_tools must be callable"


@pytest.mark.architecture
@pytest.mark.parametrize(("bc", "slice_name"), _shipped_slices_per_bc())
def test_slice_router_registered_in_routes(bc: str, slice_name: str) -> None:
    routes_module = importlib.import_module(f"cora.{bc}.routes")
    register_fn = getattr(routes_module, f"register_{bc}_routes", None)
    assert register_fn is not None, f"cora.{bc}.routes.register_{bc}_routes not found"
    src = inspect.getsource(register_fn)
    needle = f"{slice_name}.router"
    assert needle in src, (
        f"cora.{bc}.features.{slice_name} has handler.py but its router "
        f"is not included in register_{bc}_routes (looking for `{needle}`). "
        f"Every shipped slice must expose its router via app.include_router."
    )


@pytest.mark.architecture
@pytest.mark.parametrize(("bc", "slice_name"), _shipped_slices_per_bc())
def test_slice_tool_registered_in_tools(bc: str, slice_name: str) -> None:
    tools_module = importlib.import_module(f"cora.{bc}.tools")
    register_fn = getattr(tools_module, f"register_{bc}_tools", None)
    assert register_fn is not None, f"cora.{bc}.tools.register_{bc}_tools not found"
    src = inspect.getsource(register_fn)
    needle = f"{slice_name}_tool.register"
    assert needle in src, (
        f"cora.{bc}.features.{slice_name} has handler.py but its MCP tool "
        f"is not registered in register_{bc}_tools (looking for `{needle}`). "
        f"Every shipped slice must invoke <slice>_tool.register(mcp, ...)."
    )
