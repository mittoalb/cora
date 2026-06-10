"""Deterministic stream-id derivation for the ClearanceTemplate aggregate.

The ClearanceTemplate aggregate is facility-scoped, uniquely identified
by (facility_code, template_code) per [[project_slice9_design]] L7.
The event store's stream id is a UUID; we derive that UUID deterministically
from the facility code and template code with UUID5 over a fixed namespace.

Two load-bearing properties follow from this derivation:

  - **Live-path uniqueness.** Issuing `define_clearance_template`
    with the same (facility_code, template_code) pair twice produces the
    same stream_id; the second call collides on `append_streams(expected_version=0)`
    and surfaces as `ClearanceTemplateAlreadyExistsError`. No coordination required.
  - **Facility-scoped determinism.** The stream_id derivation from
    (facility_code, template_code) ensures same template code in different
    facilities produces distinct stream_ids.

`_SAFETY_CLEARANCE_TEMPLATE_NAMESPACE` is a fixed UUID4-shaped sentinel
chosen once and frozen; it MUST NOT change, or existing ClearanceTemplate
streams become unreachable. Mirrors the `_FEDERATION_FACILITY_NAMESPACE`
precedent at `cora.federation.aggregates.facility._stream_id`.
"""

from uuid import UUID, uuid5

_SAFETY_CLEARANCE_TEMPLATE_NAMESPACE = UUID("d3a8b1e0-c5e7-4f01-b2a4-9c1f2e3d4501")


def clearance_template_stream_id(facility_code: str, template_code: str) -> UUID:
    """Derive the deterministic ClearanceTemplate stream UUID.

    Facility-scoped uniqueness via (facility_code, template_code) namespace key.
    """
    return uuid5(_SAFETY_CLEARANCE_TEMPLATE_NAMESPACE, f"{facility_code}:{template_code}")


__all__ = ["clearance_template_stream_id"]
