"""The `DefinePermit` command: intent dataclass for this slice.

Carries the caller-controlled fields for defining a new Permit:

  - `peer_facility_id`: opaque string id of the peer facility this
    permit binds to. String-typed because federation peers are
    external entities; CORA does NOT mint their ids.
  - `direction`: query-convenience discriminator mirroring
    `type(terms)`. The decider enforces
    `direction == Outbound iff isinstance(terms, OutboundTerms)`.
  - `allowed_credential_ids`: bounded set of Credential ids permitted
    under this permit. Empty rejected.
  - `allowed_payload_types`: payload-type strings honored on either
    side of the relationship. Empty rejected.
  - `allowed_artifact_kinds`: artifact-kind strings honored on
    either side of the relationship. Empty rejected.
  - `abi_tier_floor`: lowest tier the permit honors.
  - `expires_at`: contractual upper bound; must lie in the future.
  - `terms`: tagged-union (`OutboundTerms | InboundTerms`) carrying
    direction-specific contractual fields per the `RunReading`
    polymorphism precedent.

Server-side concerns (new permit id, wall-clock timestamp,
correlation id, per-event ids, `defined_by_actor_id`) are injected
by the handler from infrastructure ports / the request envelope.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from cora.federation.aggregates.permit import (
    AbiTier,
    Direction,
    InboundTerms,
    OutboundTerms,
)


@dataclass(frozen=True, slots=True)
class DefinePermit:
    """Define a new Permit (genesis; lands in Defined)."""

    peer_facility_id: str
    direction: Direction
    allowed_credential_ids: frozenset[UUID]
    allowed_payload_types: frozenset[str]
    allowed_artifact_kinds: frozenset[str]
    abi_tier_floor: AbiTier
    expires_at: datetime
    terms: OutboundTerms | InboundTerms
