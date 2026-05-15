"""Every vertical slice has its required files.

Command slices need: __init__, command, decider, handler, route, tool.
Query slices need:   __init__, query, handler, route, tool.

A directory under `<bc>/features/` that has neither `command.py`
nor `query.py` is treated as a stub (in-flight, not yet wired)
and skipped. As soon as `command.py` (or `query.py`) appears,
the rest of the contract becomes mandatory.

WIP_SLICES is an explicit allowlist for slices that are mid-flight
between phases. Each entry SHOULD include a phase reference. Empty
the entry as soon as the slice ships.
"""

from pathlib import Path

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT

_COMMAND_SLICE_FILES: frozenset[str] = frozenset(
    {"__init__.py", "command.py", "decider.py", "handler.py", "route.py", "tool.py"}
)
_QUERY_SLICE_FILES: frozenset[str] = frozenset(
    {"__init__.py", "query.py", "handler.py", "route.py", "tool.py"}
)

# Slices currently in flight. Each entry MUST cite the phase that
# will close it; reviewers should reject additions that don't.
#
# Architectural exemption: entry-appending slices (Phase 8c-b
# precedent) write to a typed entries store rather than emitting
# events through a decider, so they have no `decider.py`. The
# slice contract doesn't yet have a separate file-set for this
# shape; until it does, exempt these via WIP_SLICES.
WIP_SLICES: frozenset[str] = frozenset(
    {
        "cora.decision.features.append_reasoning_entry",
        # Phase 6f-5b: append_run_reading is the second entry-appending
        # slice (after Decision's append_reasoning_entry). Same shape:
        # writes to a typed entries store via the per-category
        # ReadingStore port. Closes when the slice contract gains a
        # first-class entry-shape file-set rule (no decider.py
        # required; the architectural exemption is now n=2, justifying
        # the new file-set classification — separate cleanup).
        "cora.run.features.append_run_reading",
    }
)


def _qualified(slice_dir: Path) -> str:
    rel = slice_dir.relative_to(CORA_ROOT)
    return "cora." + ".".join(rel.parts)


def _all_slices() -> list[Path]:
    out: list[Path] = []
    for bc in BCS:
        features = CORA_ROOT / bc / "features"
        if not features.is_dir():
            continue
        for child in sorted(features.iterdir()):
            if child.is_dir() and not child.name.startswith("_"):
                out.append(child)
    return out


@pytest.mark.architecture
@pytest.mark.parametrize("slice_dir", _all_slices(), ids=_qualified)
def test_slice_has_required_files(slice_dir: Path) -> None:
    qualified = _qualified(slice_dir)
    if qualified in WIP_SLICES:
        pytest.skip(f"{qualified} is in WIP_SLICES (mid-phase)")

    files = {p.name for p in slice_dir.iterdir() if p.is_file()}
    has_command = "command.py" in files
    has_query = "query.py" in files

    if not has_command and not has_query:
        pytest.skip(f"{qualified} is a stub (no command.py or query.py)")

    assert not (has_command and has_query), (
        f"{qualified}: a slice is either a command (command.py + decider.py) or a "
        f"query (query.py), never both."
    )

    required = _COMMAND_SLICE_FILES if has_command else _QUERY_SLICE_FILES
    missing = required - files
    assert not missing, f"{qualified}: missing required files {sorted(missing)}"


@pytest.mark.architecture
def test_wip_slices_actually_exist() -> None:
    """WIP_SLICES entries must point at real directories. Drift catcher."""
    for qualified in WIP_SLICES:
        parts = qualified.split(".")
        assert parts[0] == "cora", f"{qualified}: must start with 'cora.'"
        path = CORA_ROOT.joinpath(*parts[1:])
        assert path.is_dir(), f"WIP_SLICES entry {qualified} no longer exists; remove it"
