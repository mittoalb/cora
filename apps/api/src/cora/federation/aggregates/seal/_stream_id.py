"""Deterministic stream-id derivation for the Seal singleton.

The Seal aggregate is a per-facility singleton keyed on
`facility_id` (str). The event store's stream id is still a UUID
(per the cross-aggregate convention shared by every other aggregate
read repo and by `EventStore.load`); we derive that UUID
deterministically from the facility id with UUID5 over a fixed
federation namespace. This lets every Seal slice (genesis +
transitions) target the same stream without coordinating ids out of
band, and it lets `load_seal(event_store, stream_id)` retain its
UUID-keyed signature.

`_FEDERATION_SEAL_NAMESPACE` is a fixed UUID4-shaped sentinel chosen
once and frozen; it MUST NOT change, or existing Seal streams become
unreachable. Mirrors the `_RUN_DEBRIEF_DECISION_NAMESPACE` /
`_CAUTION_DRAFTER_DECISION_NAMESPACE` precedent in
`cora.agent.subscribers`.
"""

from uuid import UUID, uuid5

_FEDERATION_SEAL_NAMESPACE = UUID("01900000-0000-7000-8000-0000fed50001")


def seal_stream_id(facility_id: str) -> UUID:
    """Derive the deterministic Seal stream UUID from a facility id."""
    return uuid5(_FEDERATION_SEAL_NAMESPACE, facility_id)


__all__ = ["seal_stream_id"]
