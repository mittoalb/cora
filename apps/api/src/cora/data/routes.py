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
    route HTTPException pathway).
  - 409 (defensive AlreadyExists): DatasetAlreadyExistsError
  - 409 (cross-aggregate refs): ProducingRunNotFoundError,
    LinkedSubjectNotFoundError, DerivedFromDatasetsNotFoundError,
    DerivedFromDatasetsDiscardedError (7b)
  - 409 (Dataset transition guards, 7b): DatasetCannotDiscardError
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.data.aggregates.dataset import (
    DatasetAlreadyExistsError,
    DatasetCannotDiscardError,
    DatasetNotFoundError,
    DerivedFromDatasetsDiscardedError,
    DerivedFromDatasetsNotFoundError,
    InvalidDatasetByteSizeError,
    InvalidDatasetChecksumError,
    InvalidDatasetDiscardReasonError,
    InvalidDatasetEncodingError,
    InvalidDatasetNameError,
    InvalidDatasetUriError,
    InvalidDerivedFromError,
    LinkedSubjectNotFoundError,
    ProducingRunNotFoundError,
)
from cora.data.errors import UnauthorizedError
from cora.data.features import discard_dataset, get_dataset, list_datasets, register_dataset


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


async def _handle_cross_agg_conflict(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for cross-aggregate-reference errors.

    `register_dataset` accepts optional refs to a Run, a Subject, and
    a set of upstream Datasets. If any referenced aggregate doesn't
    exist, the handler raises one of (ProducingRunNotFoundError,
    LinkedSubjectNotFoundError, DerivedFromDatasetsNotFoundError).
    7b adds DerivedFromDatasetsDiscardedError when one of the
    referenced lineage sources is in Discarded status. All map to
    409 because they signal a logical conflict (well-formed request,
    inconsistent with current world state).
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for state-transition guards.

    7b adds `DatasetCannotDiscardError`. All transition-state-mismatch
    errors map to 409 + `{"detail": str(exc)}`. Adding a new transition
    is one extra entry in the tuple.
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
    app.include_router(get_dataset.router)
    app.include_router(list_datasets.router)
    for validation_cls in (
        InvalidDatasetNameError,
        InvalidDatasetUriError,
        InvalidDatasetChecksumError,
        InvalidDatasetByteSizeError,
        InvalidDatasetEncodingError,
        InvalidDerivedFromError,
        InvalidDatasetDiscardReasonError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (DatasetNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (DatasetAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cross_agg_cls in (
        ProducingRunNotFoundError,
        LinkedSubjectNotFoundError,
        DerivedFromDatasetsNotFoundError,
        DerivedFromDatasetsDiscardedError,
    ):
        app.add_exception_handler(cross_agg_cls, _handle_cross_agg_conflict)
    for cannot_transition_cls in (DatasetCannotDiscardError,):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
