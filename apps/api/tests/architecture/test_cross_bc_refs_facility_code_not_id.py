"""Pin: cross-BC references to a Facility use `Facility.code` (or bare str),
NEVER the internal-opaque `FacilityId` UUID.

Per [[project_facility_aggregate_design]] L1 + [[project_structural_scope_design]]
two-tier identity contract: `Facility.id` is the opaque UUID PK for spine
references WITHIN one deployment; `Facility.code` is the cross-deployment
convergent slug used at EVERY cross-BC and cross-deployment seam (Seal
stream-id derivation, Permit.peer_facility_code, Credential.facility_code,
Calibration publish_revision, future Asset.facility_id / Supply.facility_id
binding slices).

Confusion between the two tiers would corrupt:

  - Cryptographic chain continuity on Seal (the chain anchors on
    `facility_code` string, not on `FacilityId` UUID, per the structural-
    scope memo's "Cryptographic chain continuity" lock).
  - Cross-deployment alignment (two CORA deployments naming the same
    physical facility produce identical `code` byte-for-byte but
    different `FacilityId` UUIDs).
  - Published-pointer durability (DOIs, PROV-O attributions, published
    artifact lists already embed facility codes; UUIDs would force a
    re-sign on every code value change).

The rule:

  - Aggregates OUTSIDE Federation BC may carry a facility reference as
    a bare `str` field (current state pre-slices-6-9; e.g. Seal.facility_id
    is `str`) OR as `FacilityCode` (port-surface types; current state
    post-Slice-3 e.g. CredentialLookupResult.facility_id, Calibration
    BC publish_revision signatures).
  - Aggregates OUTSIDE Federation BC MUST NOT carry a `FacilityId`
    type-annotated field. `FacilityId` lives at
    `cora.federation.aggregates._value_types` and is for spine
    references WITHIN Federation BC's Facility aggregate.

The Facility aggregate's OWN state module (`cora.federation.aggregates.facility.state`)
naturally references `FacilityId` (for `Facility.id` and `Facility.parent_id`);
that file is allowlisted. Federation features / handlers / read repos that
load Facility by id also use `FacilityId` legitimately; those are NOT
aggregate state modules and not in scope of this scan.

The companion `test_facility_id_newtype_only_in_federation_aggregates` (this
file) walks aggregate state.py files across every BC; only Federation BC's
facility/state.py is permitted to type-annotate fields as `FacilityId`.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

# Only Facility's own state module legitimately type-annotates fields as
# FacilityId. Adding a new path here requires a citation to a design
# memo that justifies the cross-aggregate FacilityId reference.
_FACILITY_ID_AGGREGATE_ALLOWLIST: frozenset[str] = frozenset(
    {
        # The Facility aggregate's own state: Facility.id + Facility.parent_id
        # are the canonical FacilityId-typed fields.
        "cora.federation.aggregates.facility.state",
    }
)

# Annotated[...] regex catches both bare `FacilityId` and `FacilityId | None`.
_FACILITY_ID_RE = re.compile(r"\bFacilityId\b")


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _aggregate_state_files() -> list[Path]:
    """Tracked `state.py` files under any BC's `aggregates/**/state.py`."""
    return sorted(
        p for p in tracked_python_files() if p.name == "state.py" and "/aggregates/" in str(p)
    )


def _annotated_field_types(class_def: ast.ClassDef) -> list[tuple[int, str]]:
    """Return (lineno, annotation source) for each annotated assignment."""
    out: list[tuple[int, str]] = []
    for node in class_def.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.append((node.lineno, ast.unparse(node.annotation)))
    return out


@pytest.mark.architecture
@pytest.mark.parametrize("path", _aggregate_state_files(), ids=_qualified)
def test_aggregate_state_does_not_type_annotate_fields_as_facility_id(path: Path) -> None:
    """Cross-BC + cross-aggregate refs to a Facility MUST use `Facility.code`
    (or bare `str`), NEVER `FacilityId`. The Facility aggregate's own state
    module is the sole allowlisted user of `FacilityId` on a state field."""
    qualified = _qualified(path)
    if qualified in _FACILITY_ID_AGGREGATE_ALLOWLIST:
        return

    tree = ast.parse(path.read_text())
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for lineno, annotation in _annotated_field_types(node):
            if _FACILITY_ID_RE.search(annotation):
                offenders.append(
                    f"line {lineno}: {node.name} field has annotation "
                    f"{annotation!r} (uses FacilityId)"
                )

    assert not offenders, (
        f"{qualified} type-annotates aggregate-state field(s) as FacilityId:\n  "
        + "\n  ".join(offenders)
        + "\n\nPer [[project_facility_aggregate_design]] L1: cross-BC and "
        "cross-aggregate references to a Facility MUST use `Facility.code` "
        "(typed as FacilityCode at port surfaces; bare str at aggregate "
        "state per the current pre-slice-6 shape on Seal / Permit / "
        "Credential). FacilityId is the internal-opaque PK for spine "
        "references WITHIN the Facility aggregate (its `id` and "
        "`parent_id` fields). If this aggregate genuinely needs to "
        "denormalize a Facility id reference (rare; requires design "
        "memo), add its qualified module name to "
        "_FACILITY_ID_AGGREGATE_ALLOWLIST in this test file with a "
        "citation to the justifying memo."
    )
