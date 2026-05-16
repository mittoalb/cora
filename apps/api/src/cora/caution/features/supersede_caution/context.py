"""Cross-aggregate context the `supersede_caution` decider validates against.

`CautionSupersessionContext` is built by the `supersede_caution`
handler from a raw `event_store.load(parent_id)` + fold call before
reaching the pure decider. The decider treats the loaded parent as
opaque domain data and validates the supersession preconditions
without performing any I/O.

Per the canonical cross-aggregate pattern documented in
CONTRIBUTING.md (and Safety BC's `ClearanceAmendmentContext`): handler
pre-loads, decider receives an immutable context dataclass, no I/O
in the decider.

Slice-local module by design: only `supersede_caution` uses it today.

## Field semantics

  - `parent`: the Caution being superseded. Decider rejects if not
    in Active status (`CautionCannotSupersedeError`). MUST not be None
    (handler raises `CautionNotFoundError` before constructing the
    context).
  - `parent_version`: the parent stream's current event-store version
    at load time. Passed straight through to
    `EventStore.append_streams` as the expected_version for the
    parent's `CautionSuperseded` append. Optimistic-concurrency guard
    against a concurrent transition on the parent.
"""

from dataclasses import dataclass

from cora.caution.aggregates.caution import Caution


@dataclass(frozen=True)
class CautionSupersessionContext:
    """Snapshot of the parent Caution + its stream version at supersede time."""

    parent: Caution
    parent_version: int
