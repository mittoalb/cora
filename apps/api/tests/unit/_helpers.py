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
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    Authorize,
    AuthzResult,
    Deny,
    EventStore,
    FixedIdGenerator,
    FrozenClock,
    LLMPort,
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
    event_store: EventStore | None = None,
    deny: bool = False,
    authorize: Authorize | None = None,
    llm: LLMPort | None = None,
) -> Kernel:
    """Build a Kernel for unit-test handler invocation.

    Defaults: FrozenClock at DEFAULT_NOW, AllowAllAuthorize, fresh
    InMemoryEventStore, fresh InMemoryIdempotencyStore, no pool. Pass
    `ids=` for the FixedIdGenerator queue (the handler consumes them
    in order: aggregate ids first, then event ids per emitted event).

    `authorize` overrides the default authorize port (use this for
    tests injecting a recording / counting / specific-reason
    Authorize stub). When `authorize` is set, `deny` is ignored.

    `llm` (Phase 8f-c iter 1) wires a test LLMPort (typically
    `FakeLLMAdapter`) when the handler under test consumes one
    (eg. `re_debrief_run`). Defaults to None so the vast majority
    of tests that don't need an LLM stay LLM-free.
    """
    if authorize is None:
        authorize = DenyAllAuthorize() if deny else AllowAllAuthorize()
    return make_inmemory_kernel(
        settings=Settings(app_env="test"),  # type: ignore[call-arg]
        clock=FrozenClock(now or DEFAULT_NOW),
        id_generator=FixedIdGenerator(list(ids or [])),
        authorize=authorize,
        event_store=event_store,
        llm=llm,
    )


__all__ = ["DEFAULT_NOW", "DenyAllAuthorize", "build_deps"]
