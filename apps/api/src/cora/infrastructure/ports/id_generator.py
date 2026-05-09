"""IdGenerator port: produces aggregate, decision, event, and command IDs.

Default adapter generates UUIDv7 (time-ordered, good for B-tree index locality
and natural sort). UUIDv7 is the standard pick for event-sourced systems where
keys are frequently inserted in roughly time order.
"""

from typing import Protocol
from uuid import UUID

import uuid_utils


class IdGenerator(Protocol):
    """Generates a fresh identifier. Same shape regardless of intended use."""

    def new_id(self) -> UUID: ...


class UUIDv7Generator:
    """Production adapter: UUIDv7 via `uuid-utils` (Rust-backed)."""

    def new_id(self) -> UUID:
        # uuid_utils.uuid7() returns a uuid_utils.UUID; convert to stdlib UUID.
        return UUID(bytes=uuid_utils.uuid7().bytes)


class FixedIdGenerator:
    """Test adapter: returns a sequence of pre-set IDs."""

    def __init__(self, ids: list[UUID]) -> None:
        self._ids = list(ids)

    def new_id(self) -> UUID:
        if not self._ids:
            msg = "FixedIdGenerator exhausted"
            raise RuntimeError(msg)
        return self._ids.pop(0)
