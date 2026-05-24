"""Application handler for the `update_asset_settings` slice.

Update-style handler — load + fold + decide + append. NOT
idempotency-wrapped (no-op-on-unchanged at the decider; HTTP-layer
caching adds no value).

**Stays longhand (does NOT use make_asset_update_handler).** This
slice is the first that needs to load MORE than just the target
Asset stream: to validate against the union of the Asset's
currently-assigned Capabilities' settings_schemas (5g-a), the
handler must also load each Family stream concurrently. The
factory's load+decide loop only knows how to read one stream;
threading a "related-streams loader" hook through the factory for
this one slice would cost more LOC than the inlined ~150 lines
saves, so this slice keeps the longhand body.

The `key_count` log field at start/success is the only externally-
visible diagnostic for the patch shape; the patch itself is captured
on the emitted event payload (post-merge, full dict) and is the
source of truth for audit.

## Two concurrency races (both knowingly accepted)

The handler's optimistic-lock guards the Asset stream write but
does NOT guard cross-stream consistency:

  1. **Family schema race**: a Family schema may be updated
     concurrently with this handler. We snapshot the schemas at
     read time; if a schema changes after our load but before our
     append, the validated dict reflects the older schema. Existing
     Asset.settings rows are never auto-revalidated when a schema
     changes (locked design; see the 5g-c memo) so this is
     consistent with the broader stance.

  2. **Family-set race**: a concurrent `add_asset_family`
     between our Asset load and our Asset append would NOT be in
     our union (its schema isn't loaded). The Asset's
     `expected_version` guard would detect the conflicting Asset
     write and raise ConcurrencyError; the operator retries and
     gets the wider union on the next attempt.

Both races are rare in practice (Capabilities and their schemas
don't churn rapidly); we accept the small window rather than
locking across streams.
"""

import asyncio
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import (
    AssetEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.family.read import load_family
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.update_asset_settings.command import UpdateAssetSettings
from cora.equipment.features.update_asset_settings.context import AssetSettingsContext
from cora.equipment.features.update_asset_settings.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

if TYPE_CHECKING:
    from cora.equipment.aggregates.family.state import Family

_STREAM_TYPE = "Asset"
_COMMAND_NAME = "UpdateAssetSettings"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every update_asset_settings handler implements."""

    async def __call__(
        self,
        command: UpdateAssetSettings,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an update_asset_settings handler closed over the shared deps."""

    async def handler(
        command: UpdateAssetSettings,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "update_asset_settings.start",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            key_count=len(command.settings_patch),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "update_asset_settings.denied",
                command_name=_COMMAND_NAME,
                asset_id=str(command.asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.asset_id,
        )
        history: list[AssetEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        # Concurrently load every assigned Family's stream so we
        # can union their schemas. If the Asset doesn't exist yet
        # (state is None), families is empty — the decider will
        # raise AssetNotFoundError anyway.
        family_ids = list(state.families) if state is not None else []
        loaded: list[Family | None] = await asyncio.gather(
            *[load_family(deps.event_store, cid) for cid in family_ids],
        )
        # Drop any None results (Family stream missing — ID
        # references a non-existent stream). Eventual-consistency
        # stance: an Asset can hold a family_id that no longer
        # corresponds to a real Family; we treat such refs as
        # schemaless rather than raising. The decider's validator
        # will tolerate unknown keys in this case (matches schemaless-
        # Family semantics).
        families = [c for c in loaded if c is not None]
        context = AssetSettingsContext(families=families)

        domain_events = decide(
            state=state,
            command=command,
            context=context,
            now=now,
        )

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=command.asset_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "update_asset_settings.success",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            key_count=len(command.settings_patch),
            family_count=len(families),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler
