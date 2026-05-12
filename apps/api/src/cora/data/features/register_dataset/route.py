"""HTTP route for the `register_dataset` slice.

`POST /datasets` returns 201 + RegisterDatasetResponse on success.
Body carries the full Dataset metadata: name, uri, checksum
(algorithm + value), byte_size, format (media_type + conforms_to),
plus the optional cross-aggregate refs.

Body shape uses nested `checksum` and `format` objects to mirror
the on-the-wire event payload, so the client-facing API and the
persisted event are byte-aligned (one less translation surface).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DATASET_CONFORMS_TO_ENTRY_MAX_LENGTH,
    DATASET_CONFORMS_TO_MAX_ENTRIES,
    DATASET_DERIVED_FROM_MAX_ENTRIES,
    DATASET_MEDIA_TYPE_MAX_LENGTH,
    DATASET_NAME_MAX_LENGTH,
    DATASET_URI_MAX_LENGTH,
)
from cora.data.features.register_dataset.command import RegisterDataset
from cora.data.features.register_dataset.handler import IdempotentHandler
from cora.infrastructure.routing import ErrorResponse, get_correlation_id, get_principal_id


class ChecksumRequest(BaseModel):
    """Bulk-content integrity hash on the registration request body."""

    algorithm: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description=(
            "Checksum algorithm name. Only 'sha256' is accepted today; "
            "the field is structured for forward-compatible algorithm "
            "addition (BLAKE3, SHA3, etc.)."
        ),
    )
    value: str = Field(
        ...,
        min_length=1,
        max_length=DATASET_CHECKSUM_SHA256_HEX_LENGTH,
        description=("Canonical checksum value. For sha256: exactly 64 lowercase hex chars."),
    )


class FormatRequest(BaseModel):
    """Structured format descriptor on the registration request body."""

    media_type: str = Field(
        ...,
        min_length=1,
        max_length=DATASET_MEDIA_TYPE_MAX_LENGTH,
        description=(
            "Loose MIME-type-ish string describing the wire format "
            "(for example 'application/x-hdf5', 'application/x-zarr')."
        ),
    )
    conforms_to: list[str] = Field(
        default_factory=list[str],
        max_length=DATASET_CONFORMS_TO_MAX_ENTRIES,
        description=(
            "Profile URIs the Dataset claims to conform to "
            "(NeXus, OME-Zarr, CIF, etc.). Empty when no profile "
            "is claimed; multi-entry when the Dataset conforms to "
            "more than one profile."
        ),
    )


class RegisterDatasetRequest(BaseModel):
    """Body for `POST /datasets`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=DATASET_NAME_MAX_LENGTH,
        description="Display name for the new Dataset.",
    )
    uri: str = Field(
        ...,
        min_length=1,
        max_length=DATASET_URI_MAX_LENGTH,
        description=(
            "Opaque URI string pointing at the bulk content "
            "(s3://, file://, https://, globus://, etc.)."
        ),
    )
    checksum: ChecksumRequest = Field(
        ...,
        description="Bulk-content integrity hash (algorithm + value).",
    )
    byte_size: int = Field(
        ...,
        ge=0,
        description=(
            "Bulk content size in bytes. Zero is valid (an empty file "
            "is a valid Dataset). Upper bound is not enforced at the BC; "
            "storage backends impose their own."
        ),
    )
    format: FormatRequest = Field(
        ...,
        description="Structured format descriptor (media_type + conforms_to profile URIs).",
    )
    producing_run_id: UUID | None = Field(
        default=None,
        description=(
            "Optional id of the Run that produced this Dataset. None for "
            "externally-sourced or pre-existing data."
        ),
    )
    subject_id: UUID | None = Field(
        default=None,
        description=(
            "Optional id of the Subject the Dataset is about. None for "
            "calibration / dark-field / synthetic data with no sample."
        ),
    )
    derived_from: list[UUID] = Field(
        default_factory=list[UUID],
        max_length=DATASET_DERIVED_FROM_MAX_ENTRIES,
        description=(
            "Optional lineage edges to other Datasets this one was "
            "derived from. Empty for raw/captured data; multi-entry for "
            "fusions / comparative derivations."
        ),
    )

    model_config = {"extra": "forbid"}


class RegisterDatasetResponse(BaseModel):
    """Response body for `POST /datasets`."""

    dataset_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.data.register_dataset
    return handler


router = APIRouter(tags=["data"])


# Per-entry conforms_to length validation: the body model can't
# express a per-element max_length on a list[str] in Pydantic
# v2 + JSON Schema cleanly, so we leave per-entry length to the
# domain VO (DatasetFormat) which raises InvalidDatasetFormatError
# (mapped to 400). The list-cardinality cap is enforced here so
# clients get 422 fast for obviously-malformed payloads.
_ = DATASET_CONFORMS_TO_ENTRY_MAX_LENGTH  # docstring reference


@router.post(
    "/datasets",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterDatasetResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": (
                "Domain invariant violated: whitespace-only name, malformed URI, "
                "non-sha256 or malformed checksum, negative byte_size, invalid "
                "format media_type, or invalid conforms_to entry."
            ),
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Cross-aggregate reference does not exist: producing_run_id, "
                "subject_id, or one or more derived_from ids."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Register a new Dataset",
)
async def post_datasets(
    body: RegisterDatasetRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key per logical request. "
                "Retries with the same key + same body return the cached "
                "response instead of re-creating the Dataset."
            ),
        ),
    ] = None,
) -> RegisterDatasetResponse:
    dataset_id = await handler(
        RegisterDataset(
            name=body.name,
            uri=body.uri,
            checksum_algorithm=body.checksum.algorithm,
            checksum_value=body.checksum.value,
            byte_size=body.byte_size,
            media_type=body.format.media_type,
            conforms_to=frozenset(body.format.conforms_to),
            producing_run_id=body.producing_run_id,
            subject_id=body.subject_id,
            derived_from=frozenset(body.derived_from),
        ),
        principal_id=principal_id,
        correlation_id=cid,
        idempotency_key=idempotency_key,
    )
    return RegisterDatasetResponse(dataset_id=dataset_id)
