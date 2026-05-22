"""The `DefineMethod` command — intent dataclass for this slice.

Carries the caller-controlled inputs:
  - `name` — display name for the new Method (the technique class)
  - `needed_families` — frozenset of Family ids the Method
    requires (eventual-consistency stance: existence not verified
    at decide time, mismatch surfaces at Plan binding in 6e)

Server-side concerns (new aggregate id, wall-clock timestamp,
correlation id, per-event ids) are injected by the handler from
infrastructure ports, matching the cross-BC create-style command
shape locked in Access / Trust / Subject / Equipment.

Status is implicit at definition (`Defined`) and not part of the
command — see Method aggregate's `state.py` docstring for the
enum-in-state, derived-from-event-type-in-evolver convention.

`needed_families` is `frozenset[UUID]` (not `list`) so the
command itself is hashable for `with_idempotency`'s SHA256 hash;
the cross-BC `_normalize_for_hash` helper sorts frozensets for
deterministic hashing across worker processes (locked in 3c).
"""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class DefineMethod:
    """Define a new abstract technique-class recipe (Method).

    `needed_supplies` is a frozenset of Supply.kind STRINGS
    the Method requires (NOT Supply instance UUIDs). Methods are
    facility-portable; the kind label resolves to a per-facility
    Supply instance at Plan-bind time. Default empty frozenset
    (sample-cleaning Methods need no supplies). Same hashability +
    `_normalize_for_hash` story as needed_families.

    `capability_id` points to the universal
    Capability template (Recipe BC 6k) this Method realizes as a
    Method-shaped executor. REQUIRED per Pattern P from
    [[project-capability-aggregate-design]] (was optional
    during the 6l-additive transition window). The handler loads
    the Capability via the cross-BC port + the decider validates
    that `Capability.executor_shapes` contains Method, raising
    `MethodCapabilityExecutorMismatchError` (409) otherwise. A
    missing Capability stream raises `CapabilityNotFoundError`
    (404) — eventual-consistency: existence is verified at handler
    time, not API-boundary time.

    Field order keeps `capability_id` before the default-factory
    collections (kwargs-only at most callsites; positional callers
    in code review get pyright-flagged on the type).
    """

    name: str
    capability_id: UUID
    needed_families: frozenset[UUID] = field(default_factory=frozenset[UUID])
    needed_supplies: frozenset[str] = field(default_factory=frozenset[str])
