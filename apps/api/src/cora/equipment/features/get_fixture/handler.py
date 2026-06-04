"""Application handler for the `get_fixture` query slice.

Query-handler shape mirrored from get_family / get_asset, but
simpler: Fixture is a single-event stream so the load is O(1) and
there's no separate lifecycle-timestamp projection to fold in. The
`registered_at` timestamp already lives on the Fixture's only event
and propagates via `load_fixture` -> `Fixture.registered_at`.

Returns the FULL Fixture state (slot_asset_bindings +
parameter_overrides + assembly_content_hash snapshot + surface_id)
so operators can see "which Assets are in this fixture". List-level
queries use the summary projection (list_fixtures); per-id get
prefers the source-of-truth event-fold.

Query handlers do NOT emit `causation_id` log fields: queries have
no causation chain (they don't emit events that downstream commands
react to). Same convention as get_family / get_asset.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.fixture import Fixture, load_fixture
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.get_fixture.query import GetFixture
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_QUERY_NAME = "GetFixture"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every get_fixture handler implements."""

    async def __call__(
        self,
        query: GetFixture,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Fixture | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a get_fixture handler closed over the shared deps."""

    async def handler(
        query: GetFixture,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Fixture | None:
        _log.info(
            "get_fixture.start",
            query_name=_QUERY_NAME,
            fixture_id=str(query.fixture_id),
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
                "get_fixture.denied",
                query_name=_QUERY_NAME,
                fixture_id=str(query.fixture_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        fixture = await load_fixture(deps.event_store, query.fixture_id)
        _log.info(
            "get_fixture.success",
            query_name=_QUERY_NAME,
            fixture_id=str(query.fixture_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=fixture is not None,
        )
        return fixture

    return handler
