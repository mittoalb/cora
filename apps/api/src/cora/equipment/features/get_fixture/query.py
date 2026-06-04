"""The `GetFixture` query - intent dataclass for this read slice.

Queries are dataclasses just like commands. Mirrors `GetFamily` /
`GetAsset`: they name the read intent and carry only the input the
caller controls; the application handler adds context
(correlation_id, principal_id) at call time.

Cross-BC pattern: queries are full vertical slices symmetric with
commands but without a decider (queries don't emit events). The
handler is a thin wrapper around the aggregate's read repository
(`load_fixture`).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GetFixture:
    """Read the current state of an existing Fixture by id."""

    fixture_id: UUID
