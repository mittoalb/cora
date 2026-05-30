"""The `ListPermits` query: intent dataclass for this read slice.

Mirrors `ListClearances`: cursor pagination + optional direction /
status / peer_facility_id filters. Each filter is optional; passing
None means "do not filter on this dimension".

`limit` defaults to 50 (capped at 100 in the route layer per the
8e-1c convention). `cursor` is opaque base64-encoded
`(defined_at, permit_id)`.

The 3 filters map 1:1 to indexed columns on
`proj_federation_permit_summary`: `direction` (text), `status`
(text), `peer_facility_id` (text). All three are projected scalar
columns; each filter renders as `column = $N` via the
`ScalarFilter` primitive.

## Expiry-range filters deferred

The Stage-2c-queries study sketched `expires_before` and
`expires_after` filters. They do NOT fit the closed set of
`list_query` filter primitives (Scalar / ArrayContains / ColumnIn)
which only express equality / membership, not range comparisons.

Per the factory's growth-rule discipline: force-conformance unless a
second consumer demands the same range shape. Ship v1 with three
equality filters; defer expiry-range to a follow-up when a second
slice needs a `ComparisonFilter` primitive. Callers needing
expiry-based pruning can fetch + filter at the call site or fetch
`get_permit` for the precise `expires_at`.
"""

from dataclasses import dataclass
from typing import Literal

PermitDirectionFilter = Literal["Outbound", "Inbound"]
PermitStatusFilter = Literal["Defined", "Active", "Suspended", "Revoked"]


@dataclass(frozen=True)
class ListPermits:
    """List permits with cursor pagination + 3-filter support."""

    cursor: str | None = None
    limit: int = 50
    direction: PermitDirectionFilter | None = None
    status: PermitStatusFilter | None = None
    peer_facility_id: str | None = None


__all__ = ["ListPermits", "PermitDirectionFilter", "PermitStatusFilter"]
