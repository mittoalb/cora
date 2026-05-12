"""Shared test helpers for unit-test handlers.

Per the Phase-8e-1c Option-4 audit + `memory/project_deferred.md`
"Test helper consolidation" entry: every BC's command/query handler
test file historically defined its own `_build_deps` function with a
near-identical body (54 instances pre-consolidation). This module
provides the canonical factory; per-BC tests migrate opportunistically
when Option 1 (spread the projection pattern) touches that BC.

## Usage

```python
from tests.unit._helpers import DEFAULT_NOW, DenyAllAuthorize, build_deps

deps = build_deps(ids=[_NEW_ID, _EVENT_ID])
deps = build_deps(ids=[...], deny=True)              # auth-deny path
deps = build_deps(ids=[...], event_store=preseeded)  # pre-seeded store
deps = build_deps(ids=[...], now=custom_clock_time)  # custom clock
```

## Design notes

- `build_deps` is a function (not a pytest fixture) so test files can
  call it from helper functions, parametrize over it, and mix it with
  module-level constants without dependency-injection ceremony.
- `DenyAllAuthorize` returns the generic reason `"denied for test"`.
  Tests asserting BC-specific deny reasons should construct their own
  Deny stub locally.
- `DEFAULT_NOW` is May 12, 2026 14:00 UTC — the canonical test clock
  used across the suite. Tests that need a specific timestamp pass
  `now=` explicitly.
- Pool stays None (in-memory test environment); Postgres-backed tests
  live in `tests/integration/` and build their own Kernel against the
  testcontainers pool.
"""

from datetime import UTC, datetime
from uuid import UUID

from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    AuthzResult,
    Deny,
    FixedIdGenerator,
    FrozenClock,
)

DEFAULT_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
"""Canonical test clock used across unit tests. Tests that need a
specific timestamp pass `now=` explicitly to `build_deps`."""


class DenyAllAuthorize:
    """Test stub that denies every authorize call with the generic
    reason `"denied for test"`. Tests asserting BC-specific deny
    reasons should construct their own Deny stub locally."""

    async def __call__(
        self,
        principal_id: UUID,
        command_name: str,
        conduit_id: UUID,
    ) -> AuthzResult:
        _ = (principal_id, command_name, conduit_id)
        return Deny(reason="denied for test")


def build_deps(
    *,
    ids: list[UUID] | None = None,
    now: datetime | None = None,
    event_store: InMemoryEventStore | None = None,
    deny: bool = False,
) -> Kernel:
    """Build a Kernel for unit-test handler invocation.

    Defaults: FrozenClock at DEFAULT_NOW, AllowAllAuthorize, fresh
    InMemoryEventStore, fresh InMemoryIdempotencyStore, no pool. Pass
    `ids=` for the FixedIdGenerator queue (the handler consumes them
    in order: aggregate ids first, then event ids per emitted event).
    """
    return Kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(now or DEFAULT_NOW),
        id_generator=FixedIdGenerator(list(ids or [])),
        authorize=DenyAllAuthorize() if deny else AllowAllAuthorize(),
        event_store=event_store or InMemoryEventStore(),
        idempotency_store=InMemoryIdempotencyStore(),
        pool=None,
    )


__all__ = ["DEFAULT_NOW", "DenyAllAuthorize", "build_deps"]
