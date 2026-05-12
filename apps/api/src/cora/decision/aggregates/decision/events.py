"""Domain events emitted by the Decision aggregate.

## Phase 8a scope

Single event: `DecisionRegistered`. The aggregate is atomic-
immutable; corrections, exceptions, appeals, and supersessions
land as NEW Decisions with `parent_id` pointing at the original
and `override_kind` explaining the transition. There is no
DecisionUpdated / DecisionRevoked / DecisionCorrected event.

## Payload conventions

  - UUIDs serialize as strings.
  - Optional fields serialize as null when None.
  - `alternatives` serializes as a list[str] preserving caller
    order (AI deciders need top-k ordering; Cedar / OPA both
    preserve it).
  - `decision_inputs` serializes as a JSON object; callers are
    responsible for ensuring values round-trip through json.dumps
    (the BC enforces shape, not value primitiveness).
  - Status is implicit (a Decision is final once registered);
    chain semantics are projection concerns, not event-payload
    concerns.

## PROV-AGENT field-name alignment (gate-review L13)

  - `actor_id` ↔ `prov:wasAssociatedWith.agent`
  - `parent_id` ↔ `prov:wasInformedBy`
  - `occurred_at` ↔ `prov:atTime`

PROV-O export at the API boundary lands when first consumer asks
(deferred-with-trigger); the in-domain payload stays on these
primitives.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, assert_never
from uuid import UUID

from cora.decision.aggregates.decision.state import (
    DecisionConfidenceSource,
    DecisionOverrideKind,
)
from cora.infrastructure.ports.event_store import StoredEvent


@dataclass(frozen=True)
class DecisionRegistered:
    """A new Decision was registered.

    All fields except `id`, `actor_id`, `context`, `choice`, and
    `occurred_at` are optional. `override_kind` requires `parent_id`
    (enforced at the decider).
    """

    decision_id: UUID
    actor_id: UUID
    context: str
    choice: str
    parent_id: UUID | None
    override_kind: DecisionOverrideKind | None
    decision_rule: str | None
    reasoning: str | None
    confidence: float | None
    confidence_source: DecisionConfidenceSource | None
    alternatives: tuple[str, ...]
    decision_inputs: dict[str, Any] | None
    reasoning_signature: str | None
    occurred_at: datetime


# Phase 8a only ships DecisionRegistered.
DecisionEvent = DecisionRegistered


def event_type_name(event: DecisionEvent) -> str:
    """Discriminator string written into StoredEvent.event_type."""
    return type(event).__name__


def to_payload(event: DecisionEvent) -> dict[str, Any]:
    """Serialize a Decision event to a JSON-friendly dict for jsonb."""
    match event:
        case DecisionRegistered(
            decision_id=decision_id,
            actor_id=actor_id,
            context=context,
            choice=choice,
            parent_id=parent_id,
            override_kind=override_kind,
            decision_rule=decision_rule,
            reasoning=reasoning,
            confidence=confidence,
            confidence_source=confidence_source,
            alternatives=alternatives,
            decision_inputs=decision_inputs,
            reasoning_signature=reasoning_signature,
            occurred_at=occurred_at,
        ):
            return {
                "decision_id": str(decision_id),
                "actor_id": str(actor_id),
                "context": context,
                "choice": choice,
                "parent_id": str(parent_id) if parent_id is not None else None,
                "override_kind": override_kind,
                "decision_rule": decision_rule,
                "reasoning": reasoning,
                "confidence": confidence,
                "confidence_source": (
                    confidence_source.value if confidence_source is not None else None
                ),
                # Caller-supplied order preserved (top-k ordering matters).
                "alternatives": list(alternatives),
                "decision_inputs": decision_inputs,
                "reasoning_signature": reasoning_signature,
                "occurred_at": occurred_at.isoformat(),
            }
        case _:  # pragma: no cover  # exhaustiveness guard
            assert_never(event)


def from_stored(stored: StoredEvent) -> DecisionEvent:
    """Rebuild a Decision event from a StoredEvent."""
    payload = stored.payload
    match stored.event_type:
        case "DecisionRegistered":
            raw_parent = payload["parent_id"]
            raw_override = payload["override_kind"]
            raw_conf_source = payload["confidence_source"]
            return DecisionRegistered(
                decision_id=UUID(payload["decision_id"]),
                actor_id=UUID(payload["actor_id"]),
                context=payload["context"],
                choice=payload["choice"],
                parent_id=UUID(raw_parent) if raw_parent is not None else None,
                override_kind=raw_override,  # already-narrow Literal value
                decision_rule=payload["decision_rule"],
                reasoning=payload["reasoning"],
                confidence=payload["confidence"],
                confidence_source=(
                    DecisionConfidenceSource(raw_conf_source)
                    if raw_conf_source is not None
                    else None
                ),
                alternatives=tuple(payload["alternatives"]),
                decision_inputs=payload["decision_inputs"],
                reasoning_signature=payload["reasoning_signature"],
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            )
        case _:
            msg = f"Unknown DecisionEvent event_type: {stored.event_type!r}"
            raise ValueError(msg)


__all__ = [
    "DecisionEvent",
    "DecisionRegistered",
    "event_type_name",
    "from_stored",
    "to_payload",
]
