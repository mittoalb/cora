"""Every command-handler `to_new_event(...)` call MUST pass `principal_id`.

Phase 9b-b enforcement. The day-1 ReBAC hook (project_authz_future)
requires that every event written to the store carries the UUID of
the principal who triggered it. The envelope helper accepts the
kwarg as optional during the 9b-a transition window; this test
ensures every handler in the codebase actually supplies it, so the
contract becomes effectively required ahead of 9b-c making it
syntactically required.

The test scans every command-handler module under `<bc>/features/
<slice>/handler.py` (plus the cross-aggregate update helpers like
`<bc>/_*_handler.py`) for any AST `Call` node whose function name
is `to_new_event`. For each such call, it asserts a keyword argument
named `principal_id` is present.

Catches future drift (a new handler that forgets to thread the
kwarg) at PR time rather than silently writing NULL principal_id
rows that would corrupt the future ReBAC graph projection's view
of ownership.

This test does NOT enforce the kwarg's *value*. The integration
test `tests/integration/test_handler_principal_id_round_trip_postgres.py`
proves a real handler call lands the right value end-to-end.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT

# Files to scan: every BC's slice-handler files plus any cross-aggregate
# update helpers at the BC root (subject/_update_handler.py,
# equipment/_asset_update_handler.py). We exclude the envelope helper
# itself (which DEFINES to_new_event) and the idempotency decorator
# (which calls handler(...) but not to_new_event).
_HANDLER_GLOB = "features/*/handler.py"
_BC_ROOT_HELPER_GLOB = "_*_handler.py"


def _handler_files() -> list[Path]:
    out: list[Path] = []
    for bc in BCS:
        bc_root = CORA_ROOT / bc
        if not bc_root.is_dir():
            continue
        out.extend(sorted(bc_root.glob(_HANDLER_GLOB)))
        out.extend(sorted(bc_root.glob(_BC_ROOT_HELPER_GLOB)))
    return out


def _qualified(handler_file: Path) -> str:
    rel = handler_file.relative_to(CORA_ROOT)
    parts = list(rel.with_suffix("").parts)
    return "cora." + ".".join(parts)


def _to_new_event_calls(tree: ast.AST) -> list[ast.Call]:
    """Find every Call node in the tree whose func resolves to a name
    `to_new_event` (either bare `to_new_event(...)` or imported
    namespace `module.to_new_event(...)`)."""
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Name) and func.id == "to_new_event") or (
            isinstance(func, ast.Attribute) and func.attr == "to_new_event"
        ):
            calls.append(node)
    return calls


@pytest.mark.unit
@pytest.mark.parametrize("handler_file", _handler_files(), ids=_qualified)
def test_handler_to_new_event_calls_pass_principal_id(handler_file: Path) -> None:
    qualified = _qualified(handler_file)
    source = handler_file.read_text()
    tree = ast.parse(source, filename=str(handler_file))

    calls = _to_new_event_calls(tree)
    if not calls:
        pytest.skip(f"{qualified} does not call to_new_event")

    missing: list[int] = []
    for call in calls:
        kwarg_names = {kw.arg for kw in call.keywords if kw.arg is not None}
        if "principal_id" not in kwarg_names:
            missing.append(call.lineno)

    assert not missing, (
        f"{qualified}: to_new_event(...) call(s) at line(s) "
        f"{sorted(missing)} do not pass `principal_id=`. "
        f"Every command handler must thread its `principal_id` kwarg "
        f"into the envelope so the day-1 ReBAC hook (see "
        f"project_authz_future) captures who triggered the event."
    )


@pytest.mark.unit
def test_handler_files_were_actually_discovered() -> None:
    """Drift catcher. If the handler-file glob breaks (BC layout
    changes, slice contract changes), this test fails loudly rather
    than the parametrized test silently passing zero parameters."""
    files = _handler_files()
    assert len(files) >= 30, (
        f"Expected at least 30 handler files across the 8 BCs, found "
        f"{len(files)}. The discovery glob may be wrong."
    )
