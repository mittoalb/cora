"""Domain events emitted by the Agent aggregate, plus the discriminated union.

Three events ship in 8f-a:

  - `AgentDefined`    -- genesis (Defined). Written to a NEW Agent
                         stream by the `define_agent` slice ATOMICALLY
                         with `ActorRegistered(kind="agent")` on the
                         Access stream via `EventStore.append_streams`.
  - `AgentVersioned`  -- transition (Defined -> Versioned). Single
                         stream.
  - `AgentDeprecated` -- transition (Defined | Versioned -> Deprecated).
                         Single stream; terminal.

`model_ref` travels in the genesis payload as a JSON-friendly dict
with `{provider, model, snapshot_pin}`. The aggregate carries the
typed `ModelRef` VO; `to_payload` and the evolver bridge typed <->
wire via primitives.

`capabilities` travels in the genesis payload as a sorted `list[str]`
(deterministic bytes for idempotency replay), reconstructed into
`frozenset[AgentCapability]` by the evolver.

`prompt_template_id` and `canonical_uri` are `UUID | None` /
`str | None` in the payload; nullable fields use `payload.get(...)`
on the read path for forward-compat.

The deprecation reason on `AgentDeprecated` is a closed bounded-text
value (not an enum); travels as `str | None` in the payload.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.agent.aggregates.agent.state import ModelRef
from cora.infrastructure.ports.event_store import StoredEvent

# ---------------------------------------------------------------------------
# ModelRef serialize / deserialize (public cross-slice helpers)
# ---------------------------------------------------------------------------


def serialize_model_ref(model_ref: ModelRef) -> dict[str, Any]:
    """Encode a typed ModelRef to a JSON-friendly dict.

    ModelRef(provider="anthropic", model="claude-sonnet-4-6",
             snapshot_pin="20251001")
      -> {"provider": "anthropic", "model": "claude-sonnet-4-6",
          "snapshot_pin": "20251001"}

    ModelRef(provider="openai", model="o4-mini", snapshot_pin=None)
      -> {"provider": "openai", "model": "o4-mini", "snapshot_pin": null}
    """
    return {
        "provider": model_ref.provider,
        "model": model_ref.model,
        "snapshot_pin": model_ref.snapshot_pin,
    }


def deserialize_model_ref(payload: dict[str, Any]) -> ModelRef:
    """Decode a JSON-friendly dict to a typed ModelRef.

    Raises ValueError on any field violation so a contaminated event
    payload fails loud at replay time.
    """
    try:
        return ModelRef(
            provider=payload["provider"],
            model=payload["model"],
            snapshot_pin=payload.get("snapshot_pin"),
        )
    except (KeyError, TypeError, AttributeError) as exc:
        msg = f"Malformed ModelRef payload {payload!r}: {exc}"
        raise ValueError(msg) from exc


# ---------------------------------------------------------------------------
# Event classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentDefined:
    """A new Agent was defined (genesis -> Defined).

    Co-written ATOMICALLY with Access BC's
    `ActorRegistered(kind="agent")` via `EventStore.append_streams`.
    The shared `agent_id` is the same UUID as the co-written Actor's
    `actor_id` (cross-BC identity sharing per
    [[project_agent_bc_design]]).

    Initial status implicitly `Defined` (event type IS the state-change
    indicator).
    """

    agent_id: UUID
    kind: str
    name: str
    version: str
    model_ref: ModelRef
    description: str | None
    canonical_uri: str | None
    prompt_template_id: UUID | None
    capabilities: frozenset[str]
    occurred_at: datetime


@dataclass(frozen=True)
class AgentVersioned:
    """A Defined Agent was promoted to Versioned (ready-for-invocation).

    Single-stream transition. The `version` value is carried for audit
    (matches the Agent's current `version` field at the time of
    promotion).
    """

    agent_id: UUID
    version: str
    occurred_at: datetime


@dataclass(frozen=True)
class AgentDeprecated:
    """An Agent was deprecated (terminal).

    Source set is `{Defined, Versioned}`. `reason` is an optional
    operator-supplied bounded-text value (1-500 chars).

    The deprecating actor's id lives on the envelope
    (`StoredEvent.principal_id`); no actor field on the payload.
    """

    agent_id: UUID
    reason: str | None
    occurred_at: datetime


# Discriminated union of every event the Agent aggregate emits.
AgentEvent = AgentDefined | AgentVersioned | AgentDeprecated


def event_type_name(event: AgentEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: AgentEvent) -> dict[str, Any]:
    """Serialise an Agent event to a JSON-friendly dict for jsonb storage.

    Primitives only: UUIDs become strings, datetimes become ISO-8601
    strings, the typed `ModelRef` becomes a sub-dict via
    `serialize_model_ref`, and `capabilities` becomes a sorted list
    (deterministic bytes for byte-for-byte idempotency replay).
    """
    match event:
        case AgentDefined(
            agent_id=agent_id,
            kind=kind,
            name=name,
            version=version,
            model_ref=model_ref,
            description=description,
            canonical_uri=canonical_uri,
            prompt_template_id=prompt_template_id,
            capabilities=capabilities,
            occurred_at=occurred_at,
        ):
            return {
                "agent_id": str(agent_id),
                "kind": kind,
                "name": name,
                "version": version,
                "model_ref": serialize_model_ref(model_ref),
                "description": description,
                "canonical_uri": canonical_uri,
                "prompt_template_id": (
                    str(prompt_template_id) if prompt_template_id is not None else None
                ),
                "capabilities": sorted(capabilities),
                "occurred_at": occurred_at.isoformat(),
            }
        case AgentVersioned(agent_id=agent_id, version=version, occurred_at=occurred_at):
            return {
                "agent_id": str(agent_id),
                "version": version,
                "occurred_at": occurred_at.isoformat(),
            }
        case AgentDeprecated(agent_id=agent_id, reason=reason, occurred_at=occurred_at):
            return {
                "agent_id": str(agent_id),
                "reason": reason,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> AgentEvent:
    """Rebuild an Agent event from a StoredEvent loaded from the event store.

    Dispatches on `stored.event_type`; raises ValueError on unknown
    discriminators so a stream contaminated with foreign event types
    fails loud rather than silently being dropped by the evolver.

    Nullable fields (`description`, `canonical_uri`,
    `prompt_template_id`, `reason`) use `payload.get(...)` for
    forward-compat.
    """
    payload = stored.payload
    match stored.event_type:
        case "AgentDefined":
            try:
                prompt_template_id_raw = payload.get("prompt_template_id")
                return AgentDefined(
                    agent_id=UUID(payload["agent_id"]),
                    kind=payload["kind"],
                    name=payload["name"],
                    version=payload["version"],
                    model_ref=deserialize_model_ref(payload["model_ref"]),
                    description=payload.get("description"),
                    canonical_uri=payload.get("canonical_uri"),
                    prompt_template_id=(
                        UUID(prompt_template_id_raw) if prompt_template_id_raw is not None else None
                    ),
                    capabilities=frozenset(payload.get("capabilities", [])),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed AgentDefined payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "AgentVersioned":
            try:
                return AgentVersioned(
                    agent_id=UUID(payload["agent_id"]),
                    version=payload["version"],
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed AgentVersioned payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case "AgentDeprecated":
            try:
                return AgentDeprecated(
                    agent_id=UUID(payload["agent_id"]),
                    reason=payload.get("reason"),
                    occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                )
            except (KeyError, TypeError, AttributeError) as exc:
                msg = f"Malformed AgentDeprecated payload {payload!r}: {exc}"
                raise ValueError(msg) from exc
        case _:
            msg = f"Unknown AgentEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "AgentDefined",
    "AgentDeprecated",
    "AgentEvent",
    "AgentVersioned",
    "deserialize_model_ref",
    "event_type_name",
    "from_stored",
    "serialize_model_ref",
    "to_payload",
]
