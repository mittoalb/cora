"""HTTP setup for the Data BC.

`register_data_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError`, `IdempotencyClaimLostError`,
`CachedHandlerError`, and `ConcurrencyError` are infra-layer errors
registered by Access (the first BC that boots). They produce
the same JSON shape regardless of which BC raised them, so Data
does not re-register them.

## Loop-collapse pattern

Each error family that maps to one HTTP status code with the same
`{"detail": str(exc)}` body shares one generic handler, registered
against a tuple of error classes via a loop. Adding a new error in
a family is one tuple entry, no new handler function. Mirrors every
other BC.

  - 400 (validation): InvalidDatasetNameError, InvalidDatasetUriError,
    InvalidDatasetChecksumError, InvalidDatasetByteSizeError,
    InvalidDatasetEncodingError, InvalidDerivedFromError,
    InvalidDatasetDiscardReasonError (7b)
  - 404: DatasetNotFoundError (raised by the discard_dataset decider
    when the target stream is empty; also surfaced by get_dataset's
    route HTTPException pathway), plus the renamed cross-aggregate
    not-found family: ProducingRunNotFoundError, LinkedSubjectNotFoundError,
    DerivedFromDatasetsNotFoundError (per the locked <X>NotFoundError -> 404
    taxonomy, clusters 2 / 4 of the 2026-05-22 audit).
  - 409 (defensive AlreadyExists): DatasetAlreadyExistsError
  - 409 (lineage state): DerivedFromDatasetsDiscardedError (referenced
    upstream Dataset is in Discarded status, a real state conflict).
  - 409 (Dataset transition guards, 7b + 7e): DatasetCannotDiscardError,
    DatasetCannotPromoteError, DatasetAlreadyPromotedError
  - 400 (validation, 7e adds): InvalidPromotionReasonError
  - 400 (validation, 12c adds): InvalidUsedCalibrationsError
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.data.aggregates.dataset import (
    DatasetAlreadyExistsError,
    DatasetAlreadyPromotedError,
    DatasetAlreadyRetractedError,
    DatasetCannotDemoteError,
    DatasetCannotDiscardError,
    DatasetCannotPromoteError,
    DatasetNotFoundError,
    DerivedFromDatasetsDiscardedError,
    DerivedFromDatasetsNotFoundError,
    InvalidDatasetByteSizeError,
    InvalidDatasetChecksumError,
    InvalidDatasetDiscardReasonError,
    InvalidDatasetEncodingError,
    InvalidDatasetNameError,
    InvalidDatasetUriError,
    InvalidDemotionReasonError,
    InvalidDerivedFromError,
    InvalidPromotionReasonError,
    InvalidUsedCalibrationsError,
    LinkedSubjectNotFoundError,
    ProducingRunNotFoundError,
)
from cora.data.aggregates.distribution import (
    DefaultStorageSupplyBootstrapError,
    DistributionAlreadyExistsError,
    DistributionByteSizeMismatchError,
    DistributionCannotRegisterOnDiscardedDatasetError,
    DistributionCannotRegisterOnNonStorageSupplyError,
    DistributionChecksumMismatchError,
    DistributionSupplyNotFoundError,
    InvalidAccessProtocolError,
    InvalidDistributionByteSizeError,
    InvalidDistributionChecksumError,
    InvalidDistributionEncodingError,
    InvalidDistributionUriError,
    UnmappedDistributionUriSchemeError,
)
from cora.data.errors import UnauthorizedError
from cora.data.features import (
    demote_dataset,
    discard_dataset,
    get_dataset,
    list_datasets,
    promote_dataset,
    register_dataset,
    register_distribution,
)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for every domain validation error (Invalid<X>...)."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def _handle_unauthorized(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    reason = exc.reason if isinstance(exc, UnauthorizedError) else str(exc)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": reason},
    )


async def _handle_not_found(request: Request, exc: Exception) -> JSONResponse:
    """Shared 404 handler for every aggregate's NotFoundError."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_already_exists(request: Request, exc: Exception) -> JSONResponse:
    """Defensive 409 handler for every aggregate's AlreadyExistsError."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_lineage_state_conflict(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for lineage-state conflicts on dataset
    registration.

    Was previously named `_handle_cross_agg_conflict` and covered
    cross-aggregate Missing*Error references too. Per the locked
    `<X>NotFoundError -> 404` taxonomy, the renamed
    `ProducingRunNotFoundError` / `LinkedSubjectNotFoundError` /
    `DerivedFromDatasetsNotFoundError` now route through
    `_handle_not_found`. The only remaining 409-mapped family here is
    `DerivedFromDatasetsDiscardedError` (referenced upstream Dataset
    is in Discarded status, a real state conflict, not a
    missing-reference). Same JSON shape as before.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for state-transition / mutation-guard errors.

    7b adds `DatasetCannotDiscardError` (Discarded terminal). 7e adds
    `DatasetCannotPromoteError` (covers Discarded / Run-not-Completed
    / lineage-not-Production branches) and `DatasetAlreadyPromotedError`
    (strict-not-idempotent re-promote). All map to 409 +
    `{"detail": str(exc)}`. Adding a new mutation guard is one
    extra entry in the tuple.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_data_routes(app: FastAPI) -> None:
    """Attach Data slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_dataset.router)
    app.include_router(discard_dataset.router)
    app.include_router(promote_dataset.router)
    app.include_router(demote_dataset.router)
    app.include_router(get_dataset.router)
    app.include_router(list_datasets.router)
    app.include_router(register_distribution.router)
    for validation_cls in (
        InvalidDatasetNameError,
        InvalidDatasetUriError,
        InvalidDatasetChecksumError,
        InvalidDatasetByteSizeError,
        InvalidDatasetEncodingError,
        InvalidDerivedFromError,
        InvalidDatasetDiscardReasonError,
        # 7e validation guard: free-form promotion reason length check.
        InvalidPromotionReasonError,
        # post-Q4 compensation slice: free-form demotion reason length check.
        InvalidDemotionReasonError,
        # 12c validation guard: cardinality cap on AsShot citation set.
        InvalidUsedCalibrationsError,
        # Distribution VO validation + lifespan-bootstrap fail-loud branches.
        # All produce {"detail": str(exc)} 400 responses. The bootstrap
        # classes are raised at app startup before any route opens; the
        # registration here is defensive in case a test-harness exercises
        # them via direct decider invocation.
        InvalidDistributionUriError,
        InvalidDistributionChecksumError,
        InvalidDistributionByteSizeError,
        InvalidDistributionEncodingError,
        InvalidAccessProtocolError,
        UnmappedDistributionUriSchemeError,
        DefaultStorageSupplyBootstrapError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (
        DatasetNotFoundError,
        # Per the locked <X>NotFoundError -> 404 taxonomy (cluster 4 of
        # the 2026-05-22 audit), the renamed cross-aggregate not-found
        # family now routes through _handle_not_found instead of the
        # old _handle_cross_agg_conflict (renamed _handle_lineage_state_conflict).
        ProducingRunNotFoundError,
        LinkedSubjectNotFoundError,
        DerivedFromDatasetsNotFoundError,
        # Distribution cross-BC not-found family.
        DistributionSupplyNotFoundError,
    ):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (
        DatasetAlreadyExistsError,
        DistributionAlreadyExistsError,
    ):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for lineage_state_cls in (DerivedFromDatasetsDiscardedError,):
        app.add_exception_handler(lineage_state_cls, _handle_lineage_state_conflict)
    for cannot_transition_cls in (
        DatasetCannotDiscardError,
        # 7e transition / promotion guards. Both surface as 409 with
        # the same body shape; cannot-promote covers Discarded /
        # Run-not-Completed / lineage-not-Production branches; already-
        # promoted is the strict-not-idempotent re-promote rejection.
        DatasetCannotPromoteError,
        DatasetAlreadyPromotedError,
        # post-Q4 compensation-slice demote guards. cannot-demote
        # covers Discarded / Trial branches; already-retracted is the
        # strict-not-idempotent re-demote rejection.
        DatasetCannotDemoteError,
        DatasetAlreadyRetractedError,
        # Distribution registration-time guards: storage-kind requirement,
        # Discarded-Dataset binding rejection, and the byte-identical-copy
        # invariants (checksum + byte_size must match parent Dataset).
        # All 409 with {"detail": str(exc)}.
        DistributionCannotRegisterOnNonStorageSupplyError,
        DistributionCannotRegisterOnDiscardedDatasetError,
        DistributionChecksumMismatchError,
        DistributionByteSizeMismatchError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
