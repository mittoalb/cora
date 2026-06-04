"""The `DetachAssetFromFixture` command - intent for the slice.

Carries the target Asset's `asset_id` and the `fixture_id` the
operator believes the Asset is currently attached to. The fixture_id
is a defensive guard: if the Asset is actually attached to a
different Fixture (or to none), the decider rejects so the operator
notices the mismatch instead of silently clearing the back-reference.

Server-side concerns (wall-clock timestamp, correlation id,
per-event id) are injected by the application handler from
infrastructure ports.

Cross-aggregate references checked by the handler before the decider:
  - asset_id must resolve to a registered Asset.

The Fixture is NOT loaded by the handler: detach only mutates the
Asset's fixture_id field, so the Fixture's state is irrelevant.
The defensive fixture_id check is purely against `asset.fixture_id`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DetachAssetFromFixture:
    """Unbind an Asset from the Fixture it is currently attached to."""

    asset_id: UUID
    fixture_id: UUID
