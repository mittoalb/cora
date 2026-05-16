"""Cross-aggregate context the `amend_clearance` decider validates against.

`ClearanceAmendmentContext` is built by the `amend_clearance` handler
from a `load_clearance(parent_id)` + raw `event_store.load(...)` call
before reaching the pure decider. The decider treats the loaded
parent as opaque domain data and validates the amendment
preconditions without performing any I/O.

This is the third slice in the codebase that takes upstream aggregate
state as input (after Plan's `define_plan` from 6e-1 and Run's
`start_run` from 6f-1). Per the canonical pattern documented in
CONTRIBUTING.md: handler pre-loads, decider receives an immutable
context dataclass, no I/O in the decider.

Slice-local module by design: only `amend_clearance` uses it today.

## Field semantics

  - `parent`: the Clearance being amended. Decider rejects if not in
    Active status (`ClearanceCannotAmendError`). MUST not be None
    (handler raises `ClearanceNotFoundError` before constructing the
    context).
  - `parent_version`: the parent stream's current event-store version
    at load time. Passed straight through to
    `EventStore.append_streams` as the expected_version for the
    parent's `ClearanceSuperseded` append. Optimistic-concurrency
    guard against a concurrent transition on the parent.
"""

from dataclasses import dataclass

from cora.safety.aggregates.clearance import Clearance


@dataclass(frozen=True)
class ClearanceAmendmentContext:
    """Snapshot of the parent Clearance + its stream version at amend time."""

    parent: Clearance
    parent_version: int
