"""Application handler for the `get_credential` query slice.

Cross-BC query-handler shape, extended to fold in projection-sourced
lifecycle timestamps per Path C (`project_template_aggregate_timestamps`):

    1. authorize(principal_id, query_name, conduit_id) -> Allow | Deny
    2. load_credential(...)              -> Credential | None  (fold-on-read)
    3. load_credential_timestamps(...)   -> CredentialLifecycleTimestamps | None
                                            (None when projection lags or
                                             pool not configured)
    4. return CredentialView             -> caller maps None to 404 / isError;
                                            maps view.timestamps fields onto
                                            the response DTO

`CredentialView` bundles the domain `Credential` with the
projection-sourced lifecycle metadata. The aggregate state stays
minimal per the Path C convention; timestamps live on the projection.
Non-HTTP/MCP consumers that only need the domain `Credential` should
call `load_credential` directly, sidestepping the projection read
entirely.

Query handlers do NOT emit `causation_id` log fields, queries have
no causation chain.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from cora.federation.aggregates.credential import (
    Credential,
    CredentialLifecycleTimestamps,
    load_credential,
    load_credential_timestamps,
)
from cora.federation.errors import UnauthorizedError
from cora.federation.features.get_credential.query import GetCredential
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetCredential"

_log = get_logger(__name__)


@dataclass(frozen=True)
class CredentialView:
    """Read-side bundle: aggregate state + projection-sourced lifecycle
    timestamps. `timestamps` is None when the projection hasn't caught
    up yet OR when the deps lack a configured pool (in-memory test
    mode); both are transient/contextual, not a Credential-not-found
    signal (use a None `CredentialView` for that)."""

    credential: Credential
    timestamps: CredentialLifecycleTimestamps | None


class Handler(Protocol):
    """Callable interface every get_credential handler implements."""

    async def __call__(
        self,
        query: GetCredential,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CredentialView | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_credential handler closed over the shared deps."""

    async def handler(
        query: GetCredential,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CredentialView | None:
        _log.info(
            "get_credential.start",
            query_name=_QUERY_NAME,
            credential_id=str(query.credential_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_credential.denied",
                query_name=_QUERY_NAME,
                credential_id=str(query.credential_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        credential = await load_credential(deps.event_store, query.credential_id)
        if credential is None:
            _log.info(
                "get_credential.success",
                query_name=_QUERY_NAME,
                credential_id=str(query.credential_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        timestamps: CredentialLifecycleTimestamps | None = None
        if deps.pool is not None:
            timestamps = await load_credential_timestamps(deps.pool, query.credential_id)

        _log.info(
            "get_credential.success",
            query_name=_QUERY_NAME,
            credential_id=str(query.credential_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
            timestamps_present=timestamps is not None,
        )
        return CredentialView(credential=credential, timestamps=timestamps)

    return handler
