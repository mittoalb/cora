"""The `DecommissionFacility` command: intent dataclass for this slice.

`facility_id` is the target Facility aggregate (the internal-opaque
UUID PK; spine reference within this deployment). `reason` is
operator-supplied free text captured at the API boundary for
audit-log breadcrumb purposes ("end-of-life", "consolidation",
"infrastructure retirement"). `reason` flows through to the
`FacilityDecommissioned` event payload so operator context survives
on the immutable event log.

The principal-id of the invoker is supplied separately by the
application handler and stamped onto the `FacilityDecommissioned`
event as `decommissioned_by`.

Terminal transition: Active -> Decommissioned. Strict-not-idempotent
at the decider: re-decommissioning an already-Decommissioned facility
raises `FacilityCannotDecommissionError` (HTTP 409) per the same
convention as `revoke_credential` / `revoke_permit`.

Code reuse anti-hook: a decommissioned facility's code stays reserved
(the projection UNIQUE INDEX on `code` covers Decommissioned rows too
per [[project_facility_aggregate_design]] L2). Re-registering with
the same code is forbidden.
"""

from dataclasses import dataclass

from cora.federation.aggregates._value_types import FacilityId


@dataclass(frozen=True, slots=True)
class DecommissionFacility:
    """Operator decommissions a Facility (terminal: Active -> Decommissioned).

    Strict-not-idempotent: decommissioning an already-Decommissioned
    facility raises `FacilityCannotDecommissionError`.
    """

    facility_id: FacilityId
    reason: str | None = None
