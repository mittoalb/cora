"""Shared route helpers for the Trust BC.

Mirrors `cora.access._routing`. The `get_correlation_id`,
`get_principal_id`, and `ErrorResponse` definitions are byte-identical
across the two BCs today (since 3f's header-based principal extraction).
Cross-BC extraction to `cora/infrastructure/_routing.py` is the
obvious next move once a third BC needs them — pure Rule of Three.
The `_bootstrap.py` module is still per-BC (each owns its own
SYSTEM_PRINCIPAL_ID fallback constant for distinguishability in logs).
"""

from typing import Annotated
from uuid import UUID

from fastapi import Header
from pydantic import BaseModel

from cora.infrastructure.observability import current_correlation_id
from cora.trust._bootstrap import SYSTEM_PRINCIPAL_ID


class ErrorResponse(BaseModel):
    """Shared error body for OpenAPI documentation."""

    detail: str


def get_correlation_id() -> UUID:
    """Derive the request's correlation UUID from the active OTel span."""
    return current_correlation_id()


def get_principal_id(
    x_principal_id: Annotated[
        UUID | None,
        Header(
            alias="X-Principal-Id",
            description=(
                "UUID of the calling principal. Production deployments MUST "
                "front the API with an auth proxy that verifies the caller's "
                "credentials, strips any client-supplied X-Principal-Id, and "
                "sets it to the verified principal UUID. The application "
                "TRUSTS this header — there is no cryptographic verification "
                "here. When absent, falls back to SYSTEM_PRINCIPAL_ID for "
                "dev / test convenience."
            ),
        ),
    ] = None,
) -> UUID:
    """Resolve the calling principal's id from the X-Principal-Id header.

    Phase 3f extraction shape: trust-the-proxy. See header docstring
    above for the production deployment requirement. Pydantic validates
    UUID format; malformed values surface as 422 before this function
    is even called. Header absent → `SYSTEM_PRINCIPAL_ID` (the Phase 1
    fallback used by tests + dev).
    """
    if x_principal_id is None:
        return SYSTEM_PRINCIPAL_ID
    return x_principal_id
