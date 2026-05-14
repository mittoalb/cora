"""Every registered projection's `apply()` source contains an
idempotency marker.

Phase-8e D11.3. The framework delivers events at-least-once; if
`apply()` is not idempotent, retries (after crash, after batch
rollback) corrupt the projection. This test enforces the contract
heuristically: each `apply()` source must contain either:

  - The substring `ON CONFLICT` (the canonical INSERT-or-UPSERT
    pattern that handles re-application as a no-op), OR
  - An explicit `# idempotent: <reason>` comment line declaring the
    projection author's reasoning (use when the operation is
    naturally idempotent, e.g. UPDATE-to-the-same-value).

Heuristic, not a proof. The whole point of this test is to make
the contract impossible to forget; reviewers still need to verify
the claim.

Skips when no projections are registered (8e-1a state).
"""

from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING

import pytest

from cora.infrastructure.projection import ProjectionRegistry
from tests.architecture.conftest import BCS

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


def _populate_registry_from_bcs() -> ProjectionRegistry:
    registry = ProjectionRegistry()
    deps_stub: Kernel | None = None
    for bc in BCS:
        try:
            module = importlib.import_module(f"cora.{bc}")
        except ModuleNotFoundError:
            continue
        register = getattr(module, f"register_{bc}_projections", None)
        if register is None:
            continue
        register(registry, deps_stub)
    return registry


@pytest.mark.architecture
def test_every_apply_carries_idempotency_marker() -> None:
    registry = _populate_registry_from_bcs()
    if registry.is_empty():
        pytest.skip(
            "No projections registered yet (8e-1a ships the framework only; "
            "8e-1b adds the first projection)."
        )

    failures: list[str] = []
    for projection in registry:
        # Scan the whole module so projections that pull SQL into
        # module-level constants (the canonical pattern for asyncpg
        # adapters in this codebase) still match the heuristic.
        module = inspect.getmodule(type(projection))
        if module is None:
            failures.append(projection.name)
            continue
        source = inspect.getsource(module)
        if "ON CONFLICT" not in source.upper() and "# idempotent:" not in source:
            failures.append(projection.name)

    assert not failures, (
        "Projections without an idempotency marker:\n"
        + "\n".join(f"  - {n}" for n in failures)
        + "\n\nEvery projection's `apply()` MUST be idempotent because the "
        "framework delivers at-least-once. Add either:\n"
        "  - An `ON CONFLICT (key) DO NOTHING/UPDATE` to your INSERT, OR\n"
        "  - A `# idempotent: <reason>` comment explaining why the "
        "operation is naturally idempotent (e.g. UPDATE-to-same-value)."
    )
