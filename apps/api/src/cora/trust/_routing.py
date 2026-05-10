"""Shared route helpers for the Trust BC.

Mirrors `cora.access._routing`. The `get_correlation_id` and
`ErrorResponse` definitions are byte-identical across BCs today; the
`get_principal_id` source differs per BC (different `_bootstrap.py`)
which is why this lives per-BC instead of being hoisted to
infrastructure. Cross-BC extraction lands once a third BC has
identical needs (Rule of Three).
"""

from uuid import UUID

from pydantic import BaseModel

from cora.infrastructure.observability import current_correlation_id
from cora.trust._bootstrap import SYSTEM_PRINCIPAL_ID


class ErrorResponse(BaseModel):
    """Shared error body for OpenAPI documentation."""

    detail: str


def get_correlation_id() -> UUID:
    """Derive the request's correlation UUID from the active OTel span."""
    return current_correlation_id()


def get_principal_id() -> UUID:
    """Resolve the calling principal's id. Phase 3a: hardcoded system principal.

    Replaced by header / token-extracted authenticated principals once
    real authentication lands.
    """
    return SYSTEM_PRINCIPAL_ID
