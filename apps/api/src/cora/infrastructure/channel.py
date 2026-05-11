"""Shared types for observation-channel declaration.

A **channel** is a header on an aggregate's main event stream that
declares an attached observation stream — a parallel, append-only
sequence of fine-grained records (per-frame triggers, motor positions,
authz traversals, etc.) that does NOT fold into the parent aggregate's
state.

The pattern is borrowed from Bluesky's `EventDescriptor` document:
the descriptor (here: `<Aggregate>ChannelOpened` event) declares the
schema and lifecycle of a stream; the per-row records (here: rows in
an `observations_<kind>` table) live elsewhere keyed by `channel_id`.

Phase 6f-5a ships this module + the Conduit aggregate's first use
(traversals channel). Run / Decision / Asset adopt the same pattern
when their first observation kind ships.

## Why these types live in shared infrastructure

Channel declarations are a cross-aggregate pattern. Run, Conduit,
Decision, Asset will all declare channels with the same shape (kind +
schema + lifecycle). The `ChannelSchema` representation needs to be
identical so observation projections can read schemas uniformly
across aggregates without per-BC adapters.

## Why the schema representation is documentation-grade today

The locked 6f-5 design (gate-review G8) keeps the schema
representation deliberately simple: a `dict[str, ChannelFieldSpec]`
with type/units/description per column. This satisfies the audit /
regulatory requirement (instrument config at time of measurement; 21
CFR Part 11, ISO 17025) without committing to a specific validator
stack. When schema validation actually matters (multi-version
channels, contract testing, schema-driven UI), this representation
can grow into a fuller model. Don't reach for JSON Schema or Pydantic
yet.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

ChannelFieldType = Literal["string", "uuid", "datetime", "int", "float", "bool"]


@dataclass(frozen=True)
class ChannelFieldSpec:
    """Declaration of one column in a channel's observation rows.

    `type` names the on-the-wire primitive type (the observation
    payload's column type); `units` is for numeric measurements
    (temperature_C, position_deg, etc.); `description` is free-text
    audit context.
    """

    type: ChannelFieldType
    units: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict for event payload storage."""
        out: dict[str, Any] = {"type": self.type}
        if self.units is not None:
            out["units"] = self.units
        if self.description is not None:
            out["description"] = self.description
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ChannelFieldSpec":
        """Rebuild from a stored dict. Defensive on missing optionals."""
        return cls(
            type=raw["type"],
            units=raw.get("units"),
            description=raw.get("description"),
        )


@dataclass(frozen=True)
class ChannelSchema:
    """Declaration of the observation-row shape a channel produces.

    `fields` maps column name to spec. Field-name uniqueness is
    enforced by the dict; ordering is irrelevant (observations are
    keyed by their own `event_id`, not by column position).

    `description` is free-text audit context for the channel as a
    whole (for example: "Eiger-9M frame trigger metadata, 21 keV,
    fly-scan tomography").
    """

    fields: dict[str, ChannelFieldSpec] = field(default_factory=dict[str, ChannelFieldSpec])
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict for event payload storage."""
        out: dict[str, Any] = {
            "fields": {name: spec.to_dict() for name, spec in self.fields.items()},
        }
        if self.description is not None:
            out["description"] = self.description
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ChannelSchema":
        """Rebuild from a stored dict."""
        raw_fields = raw.get("fields", {})
        return cls(
            fields={name: ChannelFieldSpec.from_dict(spec) for name, spec in raw_fields.items()},
            description=raw.get("description"),
        )


__all__ = [
    "ChannelFieldSpec",
    "ChannelFieldType",
    "ChannelSchema",
]
