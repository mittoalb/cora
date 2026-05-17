"""Agent aggregate state, value objects, FSM, and domain errors.

`Agent` is the config-only aggregate for the Agent BC. It carries
everything needed to identify an agent and pin its behavior for
reproducibility, but NO runtime, NO LLM invocation, NO Decision
integration (those land in 8f-b per [[project_run_debrief_design]]).

Per [[project_agent_bc_design]] the 3-state FSM is locked day one:

  Defined  -> Versioned    (via `version_agent`; ready-for-invocation)
  Defined  -> Deprecated   (via `deprecate_agent`; terminal)
  Versioned -> Deprecated  (via `deprecate_agent`; terminal)

Verb is `define` (matching Capability / Zone / Conduit / Policy
template-aggregate convention), NOT `register` (Actor / Subject /
Asset instance-shape verb). FSM matches Method / Plan / Practice /
Capability (`Defined -> Versioned -> Deprecated`). The research-memo
suggestion `Registered -> Published -> Retired` was rejected at
design lock for CORA-vocabulary-alignment and Actor-collision risk.

## VOs (bounded-text pattern reused)

`AgentKind` (1-100 chars), `AgentName` (1-100 chars), `AgentDescription`
(1-2000 chars), `AgentVersion` (1-50 chars), `AgentCanonicalURI` (1-2000
chars, must start with https://), `AgentCapability` (1-100 chars per
entry, cardinality cap 32), `AgentDeprecationReason` (1-500 chars).
All follow the `validate_bounded_text` + `object.__setattr__` pattern
hoisted in 6e-1.

`ModelRef` is a 3-field VO (`provider` + `model` + optional
`snapshot_pin`); required at definition so 8f-b's LLMPort has the
model identity available immediately.

## Cross-BC identity sharing

`Agent.id` is the SAME UUID as Access BC's `Actor.id` for the same
agent. The `define_agent` slice writes both events atomically via
`EventStore.append_streams`. `Decision.actor_id` reference checks
work uniformly regardless of whether the actor is human or agent;
no polymorphism, no saga compensation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from cora.infrastructure.bounded_text import validate_bounded_text

AGENT_KIND_MAX_LENGTH = 100
AGENT_NAME_MAX_LENGTH = 100
AGENT_DESCRIPTION_MAX_LENGTH = 2000
AGENT_VERSION_MAX_LENGTH = 50
AGENT_CANONICAL_URI_MAX_LENGTH = 2000
AGENT_CAPABILITY_MAX_LENGTH = 100
AGENT_CAPABILITIES_MAX_COUNT = 32
AGENT_DEPRECATION_REASON_MAX_LENGTH = 500
MODEL_REF_PROVIDER_MAX_LENGTH = 100
MODEL_REF_MODEL_MAX_LENGTH = 200
MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH = 100


class AgentStatus(StrEnum):
    """The Agent's lifecycle state.

    Three values locked day one per [[project_agent_bc_design]]:

      - `Defined`    -- registered as config; NOT yet ready for
                        invocation (8f-b's subscriber filters on
                        Versioned only).
      - `Versioned`  -- promoted to ready-for-invocation; rainbow-
                        deploy-style signal. Multiple Versioned
                        Agents may exist concurrently (different
                        `id`s sharing `kind`).
      - `Deprecated` -- terminal; cannot be re-Defined or re-
                        Versioned. Future invocations must pick a
                        non-Deprecated Agent of the same kind.
    """

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    DEPRECATED = "Deprecated"


# ---------------------------------------------------------------------------
# Domain validation errors (raised by VO __post_init__ + deciders)
# ---------------------------------------------------------------------------


class InvalidAgentKindError(ValueError):
    """The supplied agent kind is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Agent kind must be 1-{AGENT_KIND_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidAgentNameError(ValueError):
    """The supplied agent name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Agent name must be 1-{AGENT_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidAgentDescriptionError(ValueError):
    """The supplied agent description is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Agent description must be 1-{AGENT_DESCRIPTION_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidAgentVersionError(ValueError):
    """The supplied agent version is empty, whitespace-only, or too long.

    No semver parsing today: any 1-50 char trimmed string is accepted.
    Convention (not enforced) is semver-like (`v1`, `1.0.0`, `2026-05-16`).
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Agent version must be 1-{AGENT_VERSION_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidAgentCanonicalURIError(ValueError):
    """The supplied canonical_uri is empty, whitespace-only, too long, or not https.

    Per RFC 8707 audience shape + A2A AgentCard convention: must be a
    valid `https://` URI with no fragment, 1-2000 chars after trim.
    Loose validation today: scheme check + length check + no `#` in
    the string. Strict URI parsing deferred until A2A endpoint ships.
    """

    def __init__(self, value: str, reason: str) -> None:
        super().__init__(f"Agent canonical_uri invalid: {reason} (got: {value!r})")
        self.value = value
        self.reason = reason


class InvalidAgentCapabilityError(ValueError):
    """A supplied capability entry is empty, whitespace-only, or too long.

    Cardinality cap is enforced separately by the decider.
    """

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Agent capability must be 1-{AGENT_CAPABILITY_MAX_LENGTH} chars after trimming "
            f"(got: {value!r})"
        )
        self.value = value


class InvalidAgentCapabilitiesError(ValueError):
    """The supplied capabilities frozenset has too many entries."""

    def __init__(self, count: int) -> None:
        super().__init__(
            f"Agent capabilities must have at most {AGENT_CAPABILITIES_MAX_COUNT} entries "
            f"(got: {count})"
        )
        self.count = count


class InvalidAgentDeprecationReasonError(ValueError):
    """The supplied deprecation reason is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Agent deprecation reason must be 1-{AGENT_DEPRECATION_REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


class InvalidModelRefError(ValueError):
    """The supplied ModelRef has empty / whitespace-only / over-cap fields."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"ModelRef invalid: {reason}")
        self.reason = reason


# ---------------------------------------------------------------------------
# Aggregate-level guard errors (genesis collision / not-found / cannot-transition)
# ---------------------------------------------------------------------------


class AgentAlreadyExistsError(Exception):
    """Attempted to define an agent whose stream already has events.

    Per [[project_genesis_error_classes]] this class stays un-hoisted:
    per-BC isinstance routing in the BC's exception handler outweighs
    the ~80 LOC saved by hoisting to a generic `AggregateAlreadyExists`.
    """

    def __init__(self, agent_id: UUID) -> None:
        super().__init__(f"Agent {agent_id} already exists")
        self.agent_id = agent_id


class AgentNotFoundError(Exception):
    """Attempted an operation on an agent whose stream has no events."""

    def __init__(self, agent_id: UUID) -> None:
        super().__init__(f"Agent {agent_id} not found")
        self.agent_id = agent_id


class AgentCannotVersionError(Exception):
    """Attempted `version_agent` from a disqualifying status.

    Single-source guard: source set is `{Defined}` only. Cannot version
    an already-Versioned or Deprecated agent. Multi-version-per-kind
    is achieved by defining a new Agent with the same `kind` and a
    different `id`, not by re-versioning the same `id`.
    """

    def __init__(self, agent_id: UUID, current_status: "AgentStatus") -> None:
        super().__init__(
            f"Agent {agent_id} cannot be versioned: currently in status "
            f"{current_status.value}, version_agent requires {AgentStatus.DEFINED.value}"
        )
        self.agent_id = agent_id
        self.current_status = current_status


class AgentCannotDeprecateError(Exception):
    """Attempted `deprecate_agent` from a disqualifying status.

    Source set is `{Defined, Versioned}`. Cannot re-deprecate an
    already-Deprecated agent (strict-not-idempotent).
    """

    def __init__(self, agent_id: UUID, current_status: "AgentStatus") -> None:
        super().__init__(
            f"Agent {agent_id} cannot be deprecated: currently in status "
            f"{current_status.value}, deprecate_agent requires {AgentStatus.DEFINED.value} or "
            f"{AgentStatus.VERSIONED.value}"
        )
        self.agent_id = agent_id
        self.current_status = current_status


# ---------------------------------------------------------------------------
# Bounded-text value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentKind:
    """Free-form kind discriminator. Trimmed; 1-100 chars.

    Bare-str at MVP per Supply.kind / Procedure.kind precedent. Closed
    `AgentKind` StrEnum deferred until vocabulary stabilizes (90 days
    pilot + <10 distinct kinds; [[project_agent_bc_design]] watch
    item).

    First registered kind day-1 (in 8f-b) = `RunDebrief`.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=AGENT_KIND_MAX_LENGTH,
            error_class=InvalidAgentKindError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class AgentName:
    """Human-readable display name. Trimmed; 1-100 chars.

    Mirrors A2A AgentCard.name + OTel `gen_ai.agent.name` per the
    12-field interop identity surface in [[project_agent_bc_research]].
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=AGENT_NAME_MAX_LENGTH,
            error_class=InvalidAgentNameError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class AgentDescription:
    """Free-form description. Trimmed; 1-2000 chars.

    Mirrors A2A AgentCard.description + OTel `gen_ai.agent.description`.
    Optional at the aggregate level; required by the VO when present
    (callers pass `None` instead of an empty string).
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=AGENT_DESCRIPTION_MAX_LENGTH,
            error_class=InvalidAgentDescriptionError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class AgentVersion:
    """Semver-like version identifier. Trimmed; 1-50 chars.

    No semver parsing at MVP: any 1-50 char string is accepted.
    Convention (not enforced) is semver-like (`v1`, `1.0.0`,
    `2026-05-16`). Mirrors A2A AgentCard.version + OTel
    `gen_ai.agent.version`.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=AGENT_VERSION_MAX_LENGTH,
            error_class=InvalidAgentVersionError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class AgentCanonicalURI:
    """Optional canonical https URI. Trimmed; 1-2000 chars; must start with `https://`.

    Mirrors RFC 8707 audience + RFC 9728 + PROV-O `@id` + OTel
    `gen_ai.agent.id` per the 12-field interop identity surface.
    Loose validation today (scheme + length + no fragment); strict
    URI parsing deferred until A2A endpoint ships.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not trimmed:
            raise InvalidAgentCanonicalURIError(self.value, "empty or whitespace-only")
        if len(trimmed) > AGENT_CANONICAL_URI_MAX_LENGTH:
            raise InvalidAgentCanonicalURIError(
                self.value, f"exceeds {AGENT_CANONICAL_URI_MAX_LENGTH} chars after trim"
            )
        if not trimmed.startswith("https://"):
            raise InvalidAgentCanonicalURIError(self.value, "must start with `https://`")
        if "#" in trimmed:
            raise InvalidAgentCanonicalURIError(self.value, "must not contain a fragment (`#`)")
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class AgentCapability:
    """One free-form capability claim. Trimmed; 1-100 chars per entry.

    The aggregate carries `frozenset[AgentCapability]`. Cardinality cap
    is enforced separately by the decider. Bare-str at MVP per the
    same StrEnum-graduation precedent as AgentKind.
    """

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=AGENT_CAPABILITY_MAX_LENGTH,
            error_class=InvalidAgentCapabilityError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class AgentDeprecationReason:
    """Optional operator-supplied deprecation reason. Trimmed; 1-500 chars."""

    value: str

    def __post_init__(self) -> None:
        trimmed = validate_bounded_text(
            self.value,
            max_length=AGENT_DEPRECATION_REASON_MAX_LENGTH,
            error_class=InvalidAgentDeprecationReasonError,
        )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True)
class ModelRef:
    """Model identity: provider + model + optional snapshot pin.

    Required at `define_agent` (NOT at version_agent) so 8f-b's
    LLMPort has the model identity available the moment the Agent
    exists. Different `model_ref` = different Agent (changing model
    requires defining a new Agent with a new `id`).

    Mirrors OTel `gen_ai.system` (provider) + `gen_ai.request.model`
    (model) per [[project_agent_bc_research]] 12-field surface.
    `snapshot_pin` enables reproducibility-by-construction (Anthropic
    snapshot string, OpenAI model fingerprint, etc.).

    All three fields are trimmed and bounded; whitespace-only
    `snapshot_pin` is rejected (callers pass `None` to omit).
    """

    provider: str
    model: str
    snapshot_pin: str | None = None

    def __post_init__(self) -> None:
        provider_trimmed = self.provider.strip()
        if not provider_trimmed:
            raise InvalidModelRefError("provider must be non-empty after trim")
        if len(provider_trimmed) > MODEL_REF_PROVIDER_MAX_LENGTH:
            raise InvalidModelRefError(
                f"provider exceeds {MODEL_REF_PROVIDER_MAX_LENGTH} chars after trim"
            )

        model_trimmed = self.model.strip()
        if not model_trimmed:
            raise InvalidModelRefError("model must be non-empty after trim")
        if len(model_trimmed) > MODEL_REF_MODEL_MAX_LENGTH:
            raise InvalidModelRefError(
                f"model exceeds {MODEL_REF_MODEL_MAX_LENGTH} chars after trim"
            )

        snapshot_pin_trimmed: str | None
        if self.snapshot_pin is None:
            snapshot_pin_trimmed = None
        else:
            snapshot_pin_trimmed = self.snapshot_pin.strip()
            if not snapshot_pin_trimmed:
                raise InvalidModelRefError(
                    "snapshot_pin must be non-empty after trim if provided; pass None to omit"
                )
            if len(snapshot_pin_trimmed) > MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH:
                raise InvalidModelRefError(
                    f"snapshot_pin exceeds {MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH} chars after trim"
                )

        object.__setattr__(self, "provider", provider_trimmed)
        object.__setattr__(self, "model", model_trimmed)
        object.__setattr__(self, "snapshot_pin", snapshot_pin_trimmed)


# ---------------------------------------------------------------------------
# Agent aggregate state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Agent:
    """Aggregate root: an AI agent's typed configuration record.

    Config-only at 8f-a: no runtime, no LLM invocation, no Decision
    integration. Identity is a stable opaque `id: UUID` SHARED with
    Access BC's `Actor.id` for the same agent.

    Required day-1 fields: `id`, `kind`, `name`, `version`, `model_ref`,
    `status` (defaults to `Defined` at construction; evolver sets
    explicitly).

    Optional fields: `description`, `canonical_uri`,
    `prompt_template_id` (None at 8f-a if registry hasn't shipped a
    template; required by 8f-b's RunDebrief subscriber),
    `capabilities` (defaults to empty frozenset),
    `versioned_at` / `deprecated_at` (set by transition events).

    `defined_at` is always present (set at genesis).

    Deferred fields (per design lock):
      - `tools` (8f-c ToolGrant slices)
      - `provider_org` (A2A trigger)
      - `acts_on_behalf_of` (per-operator-agent trigger)
      - `card_signature` (A2A JWS trigger)
    """

    id: UUID
    kind: AgentKind
    name: AgentName
    version: AgentVersion
    model_ref: ModelRef
    defined_at: datetime
    description: AgentDescription | None = None
    canonical_uri: AgentCanonicalURI | None = None
    prompt_template_id: UUID | None = None
    capabilities: frozenset[AgentCapability] = field(default_factory=frozenset[AgentCapability])
    status: AgentStatus = AgentStatus.DEFINED
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None
    deprecation_reason: AgentDeprecationReason | None = None
