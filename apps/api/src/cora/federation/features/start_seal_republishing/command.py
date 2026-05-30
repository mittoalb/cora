"""The `StartSealRepublishing` command: intent dataclass for this slice.

`facility_id` is the singleton Seal's identity. The handler derives
the deterministic stream UUID from it (UUID5 with the federation
namespace) per the singleton convention locked on
`cora.federation.aggregates.seal.state`.

`reason` is a free-form operator note that captures WHY republishing
was kicked off (key compromise drill, root rotation, tree rewrite).
Not persisted on the aggregate event today; the field is kept on the
command so future audit / DecisionRegistered overlays can pick it up
without a wire break.

Server-side concerns (`started_by_actor_id`, wall-clock timestamp,
per-event ids, correlation id) are injected by the handler from
infrastructure ports / the request envelope per the non-determinism
principle (capture, don't recompute).

Strict-not-idempotent transition: starting republishing against a
Seal already in `Republishing` raises
`SealCannotStartRepublishingError` (HTTP 409).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StartSealRepublishing:
    """Operator starts a republishing window on the Live Seal (Live -> Republishing).

    Single-source: requires the Seal to be in `Live` status. The
    online key continues to sign pointers during the window;
    consumers may use the `Republishing` indicator to defer trust on
    new pointers until `complete_seal_republishing` returns the
    singleton to `Live`.
    """

    facility_id: str
    reason: str | None
