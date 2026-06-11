"""Unit tests for `RoCrate12Adapter`.

Asserts deterministic output: given fixed inputs, the byte stream
(and therefore the `content_hash`) is byte-identical across calls,
and the two invocations (`external_pid=None` vs `external_pid=<pid>`)
produce DIFFERENT hashes (per the two-content-hash model).
"""

import base64
import json
from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.data.adapters.rocrate12_serializer import RoCrate12Adapter
from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    Intent,
)
from cora.data.aggregates.dataset.state import (
    DatasetChecksum,
    DatasetEncoding,
)
from cora.data.aggregates.distribution.state import DistributionUri
from cora.data.aggregates.edition.state import (
    Creator,
    EditionKind,
    SpdxIdentifier,
)
from cora.data.ports.edition_serializer import DatasetRef
from cora.shared.facility_code import FacilityCode
from cora.shared.identifier import PersistentIdentifier, PersistentIdentifierScheme
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_EDITION_ID = UUID("01900000-0000-7000-8000-00000000ed01")
_DATASET_A = UUID("01900000-0000-7000-8000-00000000da01")
_DATASET_B = UUID("01900000-0000-7000-8000-00000000da02")
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-00000000ac70"))
_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


def _dataset_ref(dataset_id: UUID, *, byte_size: int = 1024) -> DatasetRef:
    return DatasetRef(
        dataset_id=dataset_id,
        uri=DistributionUri(f"s3://bucket/{dataset_id}.h5"),
        checksum=DatasetChecksum(algorithm="sha256", value=_GOOD_SHA256),
        byte_size=byte_size,
        encoding=DatasetEncoding(
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://nexusformat.org/"}),
        ),
        intent=Intent.PRODUCTION,
    )


@pytest.mark.unit
async def test_serialize_returns_deterministic_content_hash() -> None:
    adapter = RoCrate12Adapter()
    args: dict[str, object] = {
        "edition_id": _EDITION_ID,
        "kind": EditionKind.ROCRATE,
        "title": "Pilot",
        "dataset_refs": (_dataset_ref(_DATASET_A), _dataset_ref(_DATASET_B)),
        "publisher_facility_code": FacilityCode("cora"),
        "creators": (Creator(actor_id=_ACTOR_ID, affiliation="ANL"),),
        "publication_year": 2026,
        "license": SpdxIdentifier("CC-BY-4.0"),
        "external_pid": None,
    }
    first = await adapter.serialize(**args)  # type: ignore[arg-type]
    second = await adapter.serialize(**args)  # type: ignore[arg-type]
    assert first.content_hash == second.content_hash
    assert len(first.content_hash) == 64


@pytest.mark.unit
async def test_serialize_emits_valid_jsonld_with_expected_keys() -> None:
    adapter = RoCrate12Adapter()
    serialized = await adapter.serialize(
        edition_id=_EDITION_ID,
        kind=EditionKind.ROCRATE,
        title="Pilot",
        dataset_refs=(_dataset_ref(_DATASET_A),),
        publisher_facility_code=FacilityCode("cora"),
        creators=(Creator(actor_id=_ACTOR_ID, affiliation="ANL"),),
        publication_year=2026,
        license=SpdxIdentifier("CC-BY-4.0"),
        external_pid=None,
    )
    assert serialized.content_type == "application/ld+json"
    payload_b64 = serialized.bytes_uri.split(",", 1)[1]
    payload_bytes = base64.b64decode(payload_b64)
    document = json.loads(payload_bytes)
    assert document["@context"].startswith("https://w3id.org/ro/crate/")
    assert "@graph" in document
    types = [entry["@type"] for entry in document["@graph"] if "@type" in entry]
    assert "Dataset" in types
    assert "Organization" in types
    assert "Person" in types


@pytest.mark.unit
async def test_serialize_with_external_pid_changes_content_hash() -> None:
    adapter = RoCrate12Adapter()
    common: dict[str, object] = {
        "edition_id": _EDITION_ID,
        "kind": EditionKind.ROCRATE,
        "title": "Pilot",
        "dataset_refs": (_dataset_ref(_DATASET_A),),
        "publisher_facility_code": FacilityCode("cora"),
        "creators": (Creator(actor_id=_ACTOR_ID, affiliation="ANL"),),
        "publication_year": 2026,
        "license": SpdxIdentifier("CC-BY-4.0"),
    }
    pre = await adapter.serialize(**common, external_pid=None)  # type: ignore[arg-type]
    post = await adapter.serialize(
        **common,  # type: ignore[arg-type]
        external_pid=PersistentIdentifier(
            scheme=PersistentIdentifierScheme.DOI,
            value="10.5281/test.1234",
        ),
    )
    assert pre.content_hash != post.content_hash


@pytest.mark.unit
async def test_serialize_dataset_refs_order_independent_for_hash() -> None:
    """Hash is deterministic on logical set, not input tuple ordering."""
    adapter = RoCrate12Adapter()
    common: dict[str, object] = {
        "edition_id": _EDITION_ID,
        "kind": EditionKind.ROCRATE,
        "title": "Pilot",
        "publisher_facility_code": FacilityCode("cora"),
        "creators": (Creator(actor_id=_ACTOR_ID, affiliation="ANL"),),
        "publication_year": 2026,
        "license": None,
        "external_pid": None,
    }
    forward = await adapter.serialize(
        **common,  # type: ignore[arg-type]
        dataset_refs=(_dataset_ref(_DATASET_A), _dataset_ref(_DATASET_B)),
    )
    backward = await adapter.serialize(
        **common,  # type: ignore[arg-type]
        dataset_refs=(_dataset_ref(_DATASET_B), _dataset_ref(_DATASET_A)),
    )
    assert forward.content_hash == backward.content_hash
