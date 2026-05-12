"""Decision aggregate state, value objects, and domain errors.

`Decision` is the structured-audit record for every consequential
choice in CORA: human approval, AI inference, agent action,
operator override. The aggregate is unified across deciders, so
the same shape captures human approvers and LLM inferences alike.
The split between "AI made it" and "human made it" is a property
of `actor_id` (whose Actor.role discriminator distinguishes them)
plus optional `parent_id` chains (AI recommends → human overrides).

## What a Decision is NOT

  - Not a Run / Subject / Dataset event. Decisions are the WHY
    behind a state change; the state change itself lives on the
    target aggregate's stream.
  - Not a free-form audit log. Reasoning text is captured but
    `decision_rule` + `confidence_source` + `override_kind` etc.
    keep the structure scannable.
  - Not a place for token-by-token AI traces. Those go to a
    `reasoning` logbook on the Decision aggregate (6f-5a infra,
    integration in 8c) carrying OpenTelemetry `gen_ai.*`
    semantic-convention attributes.

## Phase 8a scope

Genesis aggregate: id + actor_id + context + choice + reasoning +
confidence + confidence_source + parent_id + decision_rule +
decision_inputs + alternatives + override_kind + reasoning_signature
+ occurred_at. Single event (DecisionRegistered); read side; REST +
MCP. Cross-aggregate validation in the handler (Actor exists; if
parent_id set, parent Decision exists).

## Standards alignment (gate-review locks; 2026 survey + validation pass)

  - **PROV-AGENT (eScience 2025)**: field naming aligns with
    `prov:wasAssociatedWith.agent` (`actor_id`),
    `prov:wasInformedBy` (`parent_id`), `prov:atTime`
    (`occurred_at`). PROV-O export at API boundaries lands when
    first consumer asks; in-domain stays on these primitives.
  - **NIST AI RMF + ISO/IEC 42001 + EU AI Act Article 12**: event
    sourcing on INSERT-only Postgres satisfies the automatic
    immutable record-keeping mandate for free.
  - **ISO 17025 Clause 7.1.3**: `decision_rule` field carries the
    documented rule; `decision_inputs` carries the measured value
    + uncertainty that fed the rule (per ILAC-G8:09/2019).
  - **OPA Decision Logs**: the `PolicyGrant` context's payload is
    isomorphic to OPA's `{decision_id, input, result, timestamp,
    metrics}` shape (`alternatives` carries the determining
    policy IDs for that context, Cedar-style).
  - **Anthropic extended thinking signature pattern**:
    `reasoning_signature` is an optional opaque blob (typically
    sha256 of the full reasoning trace, or a vendor-supplied
    encrypted summary) for tamper-evidence beyond the row-level
    INSERT-only guarantee.

## Aggregate is atomic-immutable; chains carry corrections

Decisions are append-only and never updated in place. Corrections,
exceptions, appeals, and supersessions land as NEW Decisions with
`parent_id` pointing at the original and `override_kind`
explaining the transition. The "current" Decision in a chain is
the latest entry; consumers use the `latest-in-chain wins`
projection rule (documented in this BC's `__init__.py`).

## Thirteenth bounded-name VO

`DecisionChoice` and `DecisionReasoning` use the shared
`validate_name` helper hoisted in 6e-1, with a higher max-length
cap (reasoning text is naturally longer than display names).
`DecisionContext` is intentionally an open string with documented
well-known constants, new contexts arrive without schema
migration.
"""

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from cora.infrastructure.name import validate_name

DECISION_CHOICE_MAX_LENGTH = 500
DECISION_REASONING_MAX_LENGTH = 5000
DECISION_CONTEXT_MAX_LENGTH = 100
DECISION_RULE_MAX_LENGTH = 500
DECISION_ALTERNATIVES_MAX_ENTRIES = 32
DECISION_ALTERNATIVE_ENTRY_MAX_LENGTH = 500
DECISION_INPUTS_MAX_ENTRIES = 64
DECISION_INPUTS_KEY_MAX_LENGTH = 100
DECISION_REASONING_SIGNATURE_MAX_LENGTH = 4096

# Well-known context discriminators per BC map. Open-ended: new
# contexts arrive without schema migration. Validated at
# projection time, not at write time.
DECISION_CONTEXT_RECIPE_APPROVAL = "RecipeApproval"
DECISION_CONTEXT_RUN_ABORT = "RunAbort"
DECISION_CONTEXT_RUN_STOP = "RunStop"
DECISION_CONTEXT_RUN_TRUNCATE = "RunTruncate"
DECISION_CONTEXT_RESOURCE_ALLOCATION = "ResourceAllocation"
DECISION_CONTEXT_POLICY_GRANT = "PolicyGrant"
DECISION_CONTEXT_PROCEDURE_EXECUTION = "ProcedureExecution"
DECISION_CONTEXT_DATASET_DISCARD = "DatasetDiscard"


class DecisionConfidenceSource(StrEnum):
    """How the `confidence` value was computed.

    ISO 42001 audit asks 'how was this confidence derived?'; this
    enum is the answer. Stored alongside the float so consumers can
    distinguish calibrated probabilistic estimates from
    self-reported model claims.

    Values:
      - `self_reported`: AI decider's own confidence claim, as a
        learned linguistic pattern. NOT a posterior probability.
        Lowest audit weight.
      - `logprob`: derived from token log-probabilities. Closer to
        a calibrated estimate but still model-internal.
      - `ensemble`: aggregated over multiple deciders / runs /
        models. Higher audit weight; carries the implicit promise
        of uncertainty quantification.
      - `human`: subjective human confidence rating. Audit-weight
        is operator-dependent; treat as direction-of-confidence,
        not a probability.
    """

    SELF_REPORTED = "self_reported"
    LOGPROB = "logprob"
    ENSEMBLE = "ensemble"
    HUMAN = "human"


# `override_kind` discriminator. When `parent_id` is set, this
# field says WHY the new Decision overrides the old one.
DecisionOverrideKind = Literal["correction", "exception", "appeal", "supersession"]


class InvalidDecisionChoiceError(ValueError):
    """The supplied choice is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Decision choice must be 1-{DECISION_CHOICE_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidDecisionContextError(ValueError):
    """The supplied context is empty, whitespace-only, or too long.

    Validated for shape only; the well-known-values check is a
    projection-time concern (the field is intentionally an open
    string per gate-review Q5).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Decision context must be 1-{DECISION_CONTEXT_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidDecisionReasoningError(ValueError):
    """The supplied reasoning text is empty or too long.

    Whitespace-only IS allowed (becomes None after trim); this
    differs from the bounded-name pattern because reasoning is
    naturally optional and an explicit empty string from a UI
    should fold to None rather than raise.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Decision reasoning must be at most {DECISION_REASONING_MAX_LENGTH} chars after "
            f"trimming (got length: {len(value)})"
        )
        self.value = value


class InvalidDecisionRuleError(ValueError):
    """The supplied decision_rule is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Decision rule must be 1-{DECISION_RULE_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidDecisionConfidenceError(ValueError):
    """The supplied confidence is outside [0.0, 1.0] or NaN.

    Confidence is a float in [0, 1] when present. Source is
    captured separately via `confidence_source` so consumers can
    audit the provenance of the value.
    """

    def __init__(self, value: float) -> None:
        super().__init__(f"Decision confidence must be a float in [0.0, 1.0] (got: {value!r})")
        self.value = value


class InvalidDecisionAlternativesError(ValueError):
    """The supplied alternatives tuple has too many entries, or
    an entry is empty / whitespace-only / too long.

    Cap is documented (not arbitrary): 32 entries covers the
    expected use ('operator considered Hold + Stop + Abort, chose
    Hold') plus headroom for AI top-k lists. When an AI decider
    needs more, switch to a `reasoning` logbook on the Decision
    aggregate (8c).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Decision alternatives invalid: {reason}")
        self.reason = reason


class InvalidDecisionInputsError(ValueError):
    """The supplied decision_inputs dict is too large, has an
    invalid key, or carries a non-JSON-roundtrippable value.

    Optional dict for the `decision_rule`'s input values (per ISO
    17025 Clause 7.1.3 + ILAC-G8:09/2019: a rule without its
    inputs is unauditable). Each key must be 1-100 chars after
    trim; values must be JSON-roundtrippable. Cap is 64 entries.

    JSON-roundtrip is enforced at the BC boundary via
    `json.dumps(value)`: a `datetime`, `set`, or other
    non-JSON-native value raises here rather than failing deep
    at jsonb serialization time.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Decision inputs invalid: {reason}")
        self.reason = reason


class InvalidReasoningSignatureError(ValueError):
    """The supplied reasoning_signature is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Decision reasoning_signature must be 1-{DECISION_REASONING_SIGNATURE_MAX_LENGTH} "
            f"chars after trimming (got length: {len(value)})"
        )
        self.value = value


class DecisionAlreadyExistsError(Exception):
    """Attempted to register a Decision whose stream already has events."""

    def __init__(self, decision_id: UUID) -> None:
        super().__init__(f"Decision {decision_id} already exists")
        self.decision_id = decision_id


class DecisionNotFoundError(Exception):
    """Attempted an operation on a Decision whose stream has no events."""

    def __init__(self, decision_id: UUID) -> None:
        super().__init__(f"Decision {decision_id} not found")
        self.decision_id = decision_id


class DeciderActorNotFoundError(Exception):
    """The Actor referenced by `actor_id` does not exist.

    Cross-aggregate validation at registration: the handler pre-
    loads the Actor and confirms its stream is non-empty. No
    status check (a Decision can be made by an Actor in any
    lifecycle state, including Deactivated, because the historical
    fact still holds). Mapped to HTTP 409.
    """

    def __init__(self, actor_id: UUID) -> None:
        super().__init__(f"Cannot register Decision: actor_id {actor_id} does not exist")
        self.actor_id = actor_id


class ParentDecisionNotFoundError(Exception):
    """The parent Decision referenced by `parent_id` does not exist.

    Cross-aggregate validation at registration: when `parent_id` is
    set, the handler pre-loads the parent Decision and confirms
    its stream is non-empty. Mapped to HTTP 409.
    """

    def __init__(self, parent_id: UUID) -> None:
        super().__init__(f"Cannot register Decision: parent_id {parent_id} does not exist")
        self.parent_id = parent_id


class OverrideKindRequiresParentError(ValueError):
    """`override_kind` was supplied without a `parent_id`.

    Override semantics only make sense when there's something to
    override. Either supply both or neither.
    """

    def __init__(self, override_kind: str) -> None:
        super().__init__(f"Decision override_kind={override_kind!r} requires a parent_id")
        self.override_kind = override_kind


@dataclass(frozen=True)
class DecisionChoice:
    """The choice that was made. Trimmed; 1-500 chars.

    Free-form string per gate-review Q5 (same posture as
    RunStopped reason). When a structured taxonomy crystallizes
    for a specific `context`, the conventions land as projection-
    time validation, not write-time enforcement.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_name(
            self.value,
            max_length=DECISION_CHOICE_MAX_LENGTH,
            error_class=InvalidDecisionChoiceError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class DecisionContext:
    """The decision discriminator. Trimmed; 1-100 chars.

    Open string with documented well-known values (see module-
    level constants `DECISION_CONTEXT_*`). Projection-time
    validation enforces the well-known set; the BC accepts any
    non-empty string.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_name(
            self.value,
            max_length=DECISION_CONTEXT_MAX_LENGTH,
            error_class=InvalidDecisionContextError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class DecisionRule:
    """The documented rule that governed the decision. Trimmed; 1-500 chars.

    Per ISO 17025 Clause 7.1.3, the decision rule must be
    documented and agreed before the test/calibration; reports
    must cite it. The BC accepts `decision_rule = None` for any
    context: context-conditional requiredness ("ProcedureExecution
    must carry a rule", "RecipeApproval must carry one") is a
    projection-time audit-policy concern, not a domain invariant.
    Different facilities have different rules about which contexts
    require a citation. The deferred-with-trigger is "first audit
    demand for context-strict enforcement".

    Format is free-form but the convention encourages prefixed
    identifiers like `iso17025:7.1.3:simple_acceptance` or
    `cora:policy:recipe_approval:v1`.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_name(
            self.value,
            max_length=DECISION_RULE_MAX_LENGTH,
            error_class=InvalidDecisionRuleError,
        )
        object.__setattr__(self, "value", trimmed)


def validate_reasoning(value: str | None) -> str | None:
    """Trim + bound-check the optional reasoning text.

    Returns None for None, empty string, or whitespace-only input
    (operator UIs commonly send empty strings for unset optional
    fields). Raises `InvalidDecisionReasoningError` for over-cap
    text after trim.
    """
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > DECISION_REASONING_MAX_LENGTH:
        raise InvalidDecisionReasoningError(value)
    return trimmed


def validate_confidence(value: float | None) -> float | None:
    """Bound-check the optional confidence float to [0.0, 1.0]."""
    if value is None:
        return None
    if value != value:  # NaN check (NaN != NaN)
        raise InvalidDecisionConfidenceError(value)
    if not (0.0 <= value <= 1.0):
        raise InvalidDecisionConfidenceError(value)
    return value


def validate_alternatives(value: tuple[str, ...]) -> tuple[str, ...]:
    """Validate the alternatives tuple shape + per-entry trim/length.

    Order is preserved (AI deciders need top-k ordering; Cedar /
    OPA both preserve it). Returns the trimmed tuple.
    """
    if len(value) > DECISION_ALTERNATIVES_MAX_ENTRIES:
        raise InvalidDecisionAlternativesError(
            f"too many entries (max {DECISION_ALTERNATIVES_MAX_ENTRIES}, got {len(value)})"
        )
    trimmed: list[str] = []
    for entry in value:
        entry_trimmed = entry.strip()
        if not entry_trimmed:
            raise InvalidDecisionAlternativesError("entry is empty or whitespace-only")
        if len(entry_trimmed) > DECISION_ALTERNATIVE_ENTRY_MAX_LENGTH:
            raise InvalidDecisionAlternativesError(
                f"entry exceeds {DECISION_ALTERNATIVE_ENTRY_MAX_LENGTH} chars: {entry!r}"
            )
        trimmed.append(entry_trimmed)
    return tuple(trimmed)


def validate_decision_inputs(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate optional decision_inputs dict.

    Three checks: cardinality (max 64 keys), per-key shape (1-100
    chars after trim, non-empty), per-value JSON-roundtrippability.
    The JSON check uses `json.dumps(value)` so a single
    non-roundtrippable value (datetime, set, custom object) raises
    here at the BC boundary rather than failing deep at jsonb
    serialization time.
    """
    if value is None:
        return None
    if len(value) > DECISION_INPUTS_MAX_ENTRIES:
        raise InvalidDecisionInputsError(
            f"too many entries (max {DECISION_INPUTS_MAX_ENTRIES}, got {len(value)})"
        )
    for key in value:
        key_trimmed = key.strip()
        if not key_trimmed:
            raise InvalidDecisionInputsError("key is empty or whitespace-only")
        if len(key_trimmed) > DECISION_INPUTS_KEY_MAX_LENGTH:
            raise InvalidDecisionInputsError(
                f"key exceeds {DECISION_INPUTS_KEY_MAX_LENGTH} chars: {key!r}"
            )
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise InvalidDecisionInputsError(f"value is not JSON-roundtrippable: {exc}") from exc
    return value


def validate_reasoning_signature(value: str | None) -> str | None:
    """Trim + bound-check the optional reasoning_signature."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > DECISION_REASONING_SIGNATURE_MAX_LENGTH:
        raise InvalidReasoningSignatureError(value)
    return trimmed


@dataclass(frozen=True)
class Decision:
    """Aggregate root: one structured-audit record of a consequential choice.

    Atomic-immutable: corrections / appeals / supersessions land as
    NEW Decisions with `parent_id` pointing at the original and
    `override_kind` explaining the transition. The 'current'
    Decision in a chain is the latest entry (latest-in-chain wins).
    """

    id: UUID
    actor_id: UUID
    context: DecisionContext
    choice: DecisionChoice
    parent_id: UUID | None = None
    override_kind: DecisionOverrideKind | None = None
    decision_rule: DecisionRule | None = None
    reasoning: str | None = None
    confidence: float | None = None
    confidence_source: DecisionConfidenceSource | None = None
    alternatives: tuple[str, ...] = field(default_factory=tuple[str, ...])
    decision_inputs: dict[str, Any] | None = None
    reasoning_signature: str | None = None
