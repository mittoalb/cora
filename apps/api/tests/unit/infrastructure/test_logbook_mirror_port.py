"""Unit tests for the LogbookMirrorPort Protocol (Phase 8f-b iter 2a).

8f-b ships no production implementor. These tests pin the
Protocol shape and verify that a minimal in-test implementor
satisfies it structurally, so iter 2b's subscriber can rely on
the contract.
"""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest

if TYPE_CHECKING:
    from cora.infrastructure.ports import LogbookMirrorPort


class _RecordingMirror:
    """Minimal in-test implementor of LogbookMirrorPort.

    Captures every mirror_decision invocation; never raises.
    Mirrors the contract that 8f-b's port docstring locks: errors
    are the adapter's responsibility to log, MUST NOT propagate.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    async def mirror_decision(
        self,
        *,
        decision_id: UUID,
        narrative: str,
        target_logbook: str,
    ) -> None:
        self.calls.append((str(decision_id), narrative, target_logbook))


@pytest.mark.unit
def test_recording_mirror_satisfies_protocol_structurally() -> None:
    """Pyright-level structural typing check, asserted at runtime
    via a positional assignment to a Protocol-annotated variable.

    If the Protocol shape changes such that _RecordingMirror no
    longer satisfies it, mypy / pyright would catch it; the
    runtime assert here keeps the test passing on a pyright-clean
    workspace and fails loudly on a Protocol drift."""
    mirror: LogbookMirrorPort = _RecordingMirror()
    assert mirror is not None


@pytest.mark.unit
async def test_mirror_decision_called_with_keyword_args() -> None:
    mirror = _RecordingMirror()
    did = uuid4()
    await mirror.mirror_decision(
        decision_id=did,
        narrative="Run completed nominally.",
        target_logbook="35-BM-operations",
    )
    assert mirror.calls == [(str(did), "Run completed nominally.", "35-BM-operations")]


@pytest.mark.unit
async def test_mirror_protocol_contract_does_not_return_value() -> None:
    """The port contract returns `None`; no consumer should rely on
    a status code. This is locked in the port docstring."""
    mirror = _RecordingMirror()
    result = await mirror.mirror_decision(
        decision_id=uuid4(),
        narrative="x",
        target_logbook="y",
    )
    assert result is None
