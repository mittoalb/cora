"""Policy aggregate state, value objects, domain errors, and pure evaluation.

Per ISA-99, a Policy is an authorization rule attached to a specific
Conduit: it answers "may principal P issue command C via this
Conduit". The Policy aggregate's `evaluate` function is the pure
domain-level Policy Decision Point; the `TrustAuthorize` infra
adapter (Phase 3e) wires it behind the cross-BC `Authorize` port.

Phase 3c keeps Policy minimal:
  - `id` + `name`
  - `conduit_id` — the single Conduit this policy governs (one
    policy per conduit in 3c; cross-policy resolution is 3e's
    `TrustAuthorize` problem)
  - `permitted_principals: frozenset[UUID]` — explicit allow-list
  - `permitted_commands: frozenset[str]` — command-name allow-list
    (matches the discriminator string used by the Authorize port and
    the `event_type_name` everywhere else)

Frozensets in domain state (deduplicated, hashable, set-membership
in O(1) for `evaluate`); plain lists in event payloads (JSON-friendly,
sorted for determinism). The evolver bridges the two.

Status lifecycle (`Drafted → Approved → Active → Superseded`, per
BC-map) and modify/revoke slices defer to later sub-phases per the
same additive-state pattern as Zone and Conduit.

**No referential integrity at command time.** `conduit_id` and
each entry in `permitted_principals` are stored as bare UUIDs
without verifying the referenced Conduits / Actors exist. Same
event-sourcing posture as Conduit→Zone in 3b: typos produce
"dangling" policies; downstream evaluation just denies because
the conduit_id mismatch surfaces at evaluate-time.

Empty `permitted_principals` or empty `permitted_commands` is
allowed and produces a deny-all policy by construction (every
evaluation hits the "not in {empty}" branch). Useful for
temporarily revoking access without deleting the policy.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.bounded_text import validate_bounded_text
from cora.infrastructure.ports import Allow, AuthzResult, Deny

POLICY_NAME_MAX_LENGTH = 200


class InvalidPolicyNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Policy name must be 1-{POLICY_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class PolicyAlreadyExistsError(Exception):
    """Attempted to define a policy whose stream already has events."""

    def __init__(self, policy_id: UUID) -> None:
        super().__init__(f"Policy {policy_id} already exists")
        self.policy_id = policy_id


@dataclass(frozen=True)
class PolicyName:
    """Display name for a policy. Trimmed; 1-200 chars.

    Fourth occurrence of the trimmed-bounded-name VO pattern (after
    `ActorName`, `ZoneName`, `ConduitName`). When the fifth lands and
    the bodies are still byte-identical, hoist a `BoundedName`
    factory to a cross-BC value-objects module.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=POLICY_NAME_MAX_LENGTH,
            error_class=InvalidPolicyNameError,
        )
        # Frozen dataclasses block normal assignment in __post_init__;
        # use object.__setattr__ to install the trimmed value.
        object.__setattr__(self, "value", trimmed)


_NIL_SENTINEL_ID = UUID(int=0)


@dataclass(frozen=True)
class Policy:
    """Aggregate root: an authorization rule attached to a Conduit + Surface pair.

    `surface_id` (Phase B Iter B): the process-level arrival point this
    policy gates. Defaults to nil so V1 PolicyDefined events on disk
    fold to a nil-surface policy (operationally a "match any surface"
    policy until Iter C ships surface adapters that inject real IDs).
    Once Iter C lands, the V2 bootstrap policy will bind to the
    seeded HTTP Surface and V1 will become operationally inert (per
    project_conduit_injection_design.md, V1 deprecation watch item).
    """

    id: UUID
    name: PolicyName
    conduit_id: UUID
    permitted_principals: frozenset[UUID]
    permitted_commands: frozenset[str]
    surface_id: UUID = _NIL_SENTINEL_ID


def evaluate(
    policy: Policy,
    *,
    principal_id: UUID,
    command_name: str,
    conduit_id: UUID,
    surface_id: UUID = _NIL_SENTINEL_ID,
) -> AuthzResult:
    """Pure Policy Decision Point: does `policy` permit (principal, command, conduit, surface)?

    Returns `Allow()` or `Deny(reason=...)`. The reason string is
    diagnostic — meant to flow into structlog / API responses for
    debugging, not for end-user display. Check order is cheapest-
    first: conduit mismatch → surface mismatch → principal not in
    set → command not in set.

    `surface_id` defaults to nil so existing callers (TrustAuthorize
    pre-Iter-B + tests pre-Iter-B + handler call sites pre-Iter-C)
    keep working unchanged. A V1 policy with `policy.surface_id ==
    UUID(int=0)` matches a call with `surface_id=UUID(int=0)` (the
    transitional state). Once Iter C ships real surface adapters,
    nil-surface calls disappear and V1 policies cease to match
    anything in production — operators promote V2 (per
    SYSTEM_BOOTSTRAP_POLICY_V2_ID).

    Living in `state.py` because it's a pure operation on Policy
    state (no I/O, no awaits, no mutation). If `state.py` exceeds
    ~200 lines or more pure operations land here, split into a
    dedicated `aggregates/policy/evaluate.py`.
    """
    if conduit_id != policy.conduit_id:
        return Deny(
            reason=(f"Policy {policy.id} governs conduit {policy.conduit_id}, not {conduit_id}")
        )
    if surface_id != policy.surface_id:
        return Deny(
            reason=(f"Policy {policy.id} governs surface {policy.surface_id}, not {surface_id}")
        )
    if principal_id not in policy.permitted_principals:
        return Deny(reason=f"Principal {principal_id} not in policy {policy.id}'s permitted set")
    if command_name not in policy.permitted_commands:
        return Deny(reason=(f"Command {command_name!r} not in policy {policy.id}'s permitted set"))
    return Allow()
