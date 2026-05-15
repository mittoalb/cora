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
`<bc>/_*_handler.py` and the cross-BC update factory at
`infrastructure/update_handler.py`) for any AST `Call` node whose
function name is `to_new_event`. For each such call, it asserts a
keyword argument named `principal_id` is present.

The cross-BC factory (`cora.infrastructure.update_handler`) is the
single `to_new_event` call site for every slice that uses
`make_<aggregate>_update_handler` (Subject / Asset / Run / Method /
Practice / Plan / Supply / Procedure), so its inclusion in the scan
is load-bearing — without it, ~36 slices would be silently uncovered.

## Skip categories (see `_classify_skip_reason`)

When a handler file contains zero `to_new_event` calls the test
skips with a categorized message so a future reader sees at a glance
which architectural pattern explains the skip:

  (a) read-style query handler -- emits no events (identified by a
      `query.py` sibling file in the slice directory; covers
      get_* / list_* / evaluate_*)
  (b) update-style slice that delegates to the BC-local factory
      wrapper (identified by an import of `make_*_update_handler`)
      -- the actual to_new_event call is at the cross-BC factory,
      which IS asserted directly
  (c) BC-root factory wrapper file (`<bc>/_<aggregate>_update_handler.py`)
      -- thin closure over the cross-BC factory; same coverage path
      as (b)

A skip with the "uncategorized" message is a coverage gap and
should be classified explicitly (extend `_classify_skip_reason`).

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
# equipment/_asset_update_handler.py, etc.) plus the cross-BC update
# factory at infrastructure/update_handler.py (the single to_new_event
# call site for every slice that delegates to make_<aggregate>_update_handler).
# We exclude the envelope helper itself (which DEFINES to_new_event) and
# the idempotency decorator (which calls handler(...) but not to_new_event).
_HANDLER_GLOB = "features/*/handler.py"
_BC_ROOT_HELPER_GLOB = "_*_handler.py"
_CROSS_BC_FACTORY = CORA_ROOT / "infrastructure" / "update_handler.py"


def _handler_files() -> list[Path]:
    out: list[Path] = []
    for bc in BCS:
        bc_root = CORA_ROOT / bc
        if not bc_root.is_dir():
            continue
        out.extend(sorted(bc_root.glob(_HANDLER_GLOB)))
        out.extend(sorted(bc_root.glob(_BC_ROOT_HELPER_GLOB)))
    if _CROSS_BC_FACTORY.is_file():
        out.append(_CROSS_BC_FACTORY)
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


def _classify_skip_reason(handler_file: Path, tree: ast.AST) -> str:
    """Explain WHY this file has no `to_new_event` call.

    Three categories cover every skip case so a future reader can see
    at a glance whether each skip is benign or a coverage gap. The
    architectural invariant ('every event carries principal_id') is
    upheld for categories (a) trivially (no events emitted) and (b/c)
    transitively (the cross-BC factory at cora.infrastructure.update_handler
    is the single asserted call site).
    """
    rel = handler_file.relative_to(CORA_ROOT)
    parts = rel.with_suffix("").parts

    # (c) BC-root factory wrapper file: <bc>/_<aggregate>_update_handler.py.
    # Thin closure that delegates to the cross-BC factory; the factory's
    # to_new_event call site is asserted directly.
    if len(parts) == 2 and parts[1].startswith("_") and "update_handler" in parts[1]:
        return (
            "BC-root factory wrapper: delegates to "
            "cora.infrastructure.update_handler (asserted there)"
        )

    # (a) Read-style query handler: identified by a `query.py` sibling
    # file in the slice directory (vs `command.py` for command slices —
    # the canonical slice-contract distinction enforced by
    # test_slice_contract.py). Covers get_* / list_* / evaluate_* and
    # any future query-shape slice naming.
    if len(parts) == 4 and parts[1] == "features" and parts[3] == "handler":
        slice_dir = handler_file.parent
        if (slice_dir / "query.py").is_file():
            return "read-style query handler: emits no events"

        # (b) Update-style slice handler that delegates to the BC-local
        # factory wrapper. Identified by an import of `make_*_update_handler`.
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    if alias.name.startswith("make_") and alias.name.endswith("_update_handler"):
                        return (
                            f"update-style slice: delegates to {alias.name} "
                            "(the cross-BC to_new_event call site is asserted at "
                            "cora.infrastructure.update_handler)"
                        )

    # Uncategorized. Should not fire today; if it does, the file is a
    # genuine coverage gap and the test author should classify it.
    return "no to_new_event call (uncategorized: file may need explicit classification)"


@pytest.mark.architecture
@pytest.mark.parametrize("handler_file", _handler_files(), ids=_qualified)
def test_handler_to_new_event_calls_pass_principal_id(handler_file: Path) -> None:
    qualified = _qualified(handler_file)
    source = handler_file.read_text()
    tree = ast.parse(source, filename=str(handler_file))

    calls = _to_new_event_calls(tree)
    if not calls:
        pytest.skip(f"{qualified}: {_classify_skip_reason(handler_file, tree)}")

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


@pytest.mark.architecture
def test_handler_files_were_actually_discovered() -> None:
    """Drift catcher. If the handler-file glob breaks (BC layout
    changes, slice contract changes), this test fails loudly rather
    than the parametrized test silently passing zero parameters."""
    files = _handler_files()
    assert len(files) >= 30, (
        f"Expected at least 30 handler files across the 8 BCs, found "
        f"{len(files)}. The discovery glob may be wrong."
    )
