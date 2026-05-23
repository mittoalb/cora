"""Every command/query handler Protocol MUST accept a `surface_id` kwarg.

Every BC's handler Protocol accepts `surface_id` and routes it through
to `authorize()`. This test pins that invariant against future drift:
a new slice landing without `surface_id` would silently degrade to
the V1-wildcard nil sentinel, bypassing whichever V2 per-surface
policy was meant to gate the call once V2 policies are seeded.

The shape mirrors `test_envelope_principal_id.py`: parametrize over
every git-tracked `features/<slice>/handler.py` (plus BC-root update
helpers like `<bc>/_*_handler.py` and the cross-BC factories at
`infrastructure/{update_handler,list_query,idempotency}.py`), AST-walk
for `class Handler(Protocol)` and `class IdempotentHandler(Protocol)`
class definitions, and assert each Protocol's `__call__` method's
keyword-only arguments include `surface_id`.

## Skip categories

When a handler file contains zero `Handler` / `IdempotentHandler`
Protocols, the test skips with a categorized message:

  (a) BC-root factory wrapper (`<bc>/_<aggregate>_update_handler.py`):
      thin closure that doesn't redeclare the Protocol; the cross-BC
      factory's Protocol IS asserted directly
  (b) cross-BC factory at `infrastructure/{update_handler,list_query,
      idempotency}.py` carries its own Protocol; included in the
      asserted set

This test does NOT enforce that handlers FORWARD surface_id to
`deps.authz.authorize()`. That's covered by a separate test (planned) +
end-to-end coverage in `tests/unit/trust/test_policy.py`.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files

_HANDLER_SUFFIX = "/features/"
_BC_ROOT_HELPER_MARKER = "_handler.py"
_CROSS_BC_FACTORIES = (
    CORA_ROOT / "infrastructure" / "update_handler.py",
    CORA_ROOT / "infrastructure" / "list_query.py",
    CORA_ROOT / "infrastructure" / "idempotency.py",
)


def _handler_files() -> list[Path]:
    tracked = tracked_python_files()
    out: list[Path] = []
    for path in sorted(tracked):
        rel = path.relative_to(CORA_ROOT) if path.is_relative_to(CORA_ROOT) else None
        if rel is None:
            continue
        parts = rel.parts
        if not parts:
            continue
        bc = parts[0]
        if bc not in BCS:
            continue
        # Slice handler: <bc>/features/<slice>/handler.py
        if len(parts) == 4 and parts[1] == "features" and parts[3] == "handler.py":
            out.append(path)
            continue
        # BC-root update helper: <bc>/_<aggregate>_handler.py
        if (
            len(parts) == 2
            and parts[1].startswith("_")
            and parts[1].endswith(_BC_ROOT_HELPER_MARKER)
        ):
            out.append(path)
    for factory in _CROSS_BC_FACTORIES:
        if factory in tracked:
            out.append(factory)
    return out


def _qualified(handler_file: Path) -> str:
    rel = handler_file.relative_to(CORA_ROOT)
    return "cora." + ".".join(rel.with_suffix("").parts)


def _handler_protocol_classes(tree: ast.AST) -> list[ast.ClassDef]:
    """Find every `class Handler(Protocol)` or `class IdempotentHandler(Protocol)`
    class def, plus any cross-BC factory naming variant (`_BareHandler`,
    `_IdempotentHandler`, `_UpdateHandler`, etc.) that inherits from
    `Protocol`."""
    out: list[ast.ClassDef] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        # Bases must reference Protocol (bare or namespaced).
        inherits_protocol = any(
            (isinstance(base, ast.Name) and base.id == "Protocol")
            or (isinstance(base, ast.Attribute) and base.attr == "Protocol")
            for base in node.bases
        )
        if not inherits_protocol:
            continue
        # Name heuristic: ends with "Handler" (covers Handler, IdempotentHandler,
        # _BareHandler, _IdempotentHandler, _UpdateHandler, _QueryHandler).
        if not node.name.endswith("Handler"):
            continue
        out.append(node)
    return out


def _call_method_kwargs(cls: ast.ClassDef) -> set[str] | None:
    """Return the keyword-only arg names of the class's `__call__` method,
    or None if no `__call__` is declared."""
    for body_node in cls.body:
        if not isinstance(body_node, ast.AsyncFunctionDef | ast.FunctionDef):
            continue
        if body_node.name != "__call__":
            continue
        return {arg.arg for arg in body_node.args.kwonlyargs}
    return None


def _classify_skip_reason(handler_file: Path) -> str:
    rel = handler_file.relative_to(CORA_ROOT)
    parts = rel.parts
    if len(parts) == 2 and parts[1].startswith("_") and parts[1].endswith(_BC_ROOT_HELPER_MARKER):
        return (
            "BC-root factory wrapper: re-uses the cross-BC factory's "
            "Protocol (asserted at cora.infrastructure.{update_handler,"
            "list_query,idempotency})"
        )
    return "no Handler/IdempotentHandler Protocol class (uncategorized)"


@pytest.mark.architecture
@pytest.mark.parametrize("handler_file", _handler_files(), ids=_qualified)
def test_handler_protocol_accepts_surface_id(handler_file: Path) -> None:
    qualified = _qualified(handler_file)
    source = handler_file.read_text()
    tree = ast.parse(source, filename=str(handler_file))

    protocols = _handler_protocol_classes(tree)
    if not protocols:
        pytest.skip(f"{qualified}: {_classify_skip_reason(handler_file)}")

    offenders: list[str] = []
    for cls in protocols:
        kwargs = _call_method_kwargs(cls)
        if kwargs is None:
            continue  # Protocol with no __call__ — not a handler shape
        if "surface_id" not in kwargs:
            offenders.append(f"{cls.name} (line {cls.lineno})")

    assert not offenders, (
        f"{qualified}: Handler Protocol(s) missing `surface_id` kwarg: "
        f"{', '.join(offenders)}. Every handler Protocol must accept "
        f"`surface_id: UUID` (defaults to the nil "
        f"sentinel for V1 compatibility). Any new slice must follow the "
        f"same shape so V2 per-surface policies (forthcoming) gate the "
        f"call site correctly."
    )


@pytest.mark.architecture
def test_handler_files_were_actually_discovered() -> None:
    """Drift catcher: if the discovery glob breaks, this test fails
    loudly rather than the parametrized test silently passing zero
    parameters."""
    files = _handler_files()
    assert len(files) >= 100, (
        f"Expected at least 100 handler files across the 15 BCs, found "
        f"{len(files)}. The discovery glob may be wrong."
    )
