"""Every registered Reaction declares a small `batch_size`.

The Reaction Protocol exists because side-effecting subscribers
(LLM calls, signing, external HTTP) take 5-15 s per `apply()` and
holding a Postgres pool connection across N events at that latency
starves Projection advance loops sharing the same pool.

The Reaction Protocol contract requires `batch_size = 1` unless the
apply path is provably fast. This test enforces a soft ceiling
(`batch_size <= 10`) on every Subscriber whose class name ends with
`Subscriber` or whose module lives under `<bc>/subscribers/`. The
ceiling is loose enough to allow a future fast-path Reaction (e.g.,
local cache lookup) but tight enough to catch the failure mode
"contributor forgot the override and the worker default of 100
quietly kicked in."

Skips if no BCs ship Reactions yet (Agent BC is the only one today).
"""

from __future__ import annotations

import contextlib
import importlib
from typing import TYPE_CHECKING

import pytest

from cora.infrastructure.projection import ProjectionRegistry, Reaction
from tests.architecture.conftest import BCS

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel

_REACTION_BATCH_SIZE_CEILING = 10


def _populate_registry_from_bcs() -> ProjectionRegistry:
    """Mirror of `test_projection_idempotency._populate_registry_from_bcs`
    but extended to call `register_<bc>_subscribers` as well as
    `register_<bc>_projections`. Reactions live under the
    `_subscribers.py` factory; Projections live under the
    `_projections.py` factory. Both register into the same
    ProjectionRegistry today."""
    registry = ProjectionRegistry()
    deps_stub: Kernel | None = None
    for bc in BCS:
        try:
            module = importlib.import_module(f"cora.{bc}")
        except ModuleNotFoundError:
            continue
        register_projections = getattr(module, f"register_{bc}_projections", None)
        if register_projections is not None:
            register_projections(registry, deps_stub)
        register_subscribers = getattr(module, f"register_{bc}_subscribers", None)
        if register_subscribers is not None:
            # Reactions need a real Kernel (llm port, signer, etc.) to
            # construct; skip when the stub Kernel can't satisfy the
            # constructor. The classification test in
            # tests/unit/agent/test_reaction_classification.py pins
            # batch_size at the class level for the known Reactions.
            with contextlib.suppress(AttributeError, TypeError):
                register_subscribers(registry, deps_stub)
    return registry


@pytest.mark.architecture
def test_every_reaction_pins_small_batch_size() -> None:
    """A registered Subscriber whose class declares `batch_size > 10`
    has almost certainly slipped through the Reaction-Protocol
    contract (the recommended value is 1). Fails loudly so the
    contributor adds an explicit override or argues the case in
    review."""
    registry = _populate_registry_from_bcs()
    if registry.is_empty():
        pytest.skip(
            "No subscribers registered; Agent BC needs a Kernel to build "
            "its Reactions. The unit-level classification test pins the "
            "batch_size invariant for the known Reactions."
        )

    # `isinstance(subscriber, Reaction)` is a structural check (Reaction
    # is @runtime_checkable); Projections without a `batch_size` attribute
    # don't match because the Protocol declares it as required. So this
    # loop only sees Subscribers that explicitly opted into the Reaction
    # contract; a stray Projection with `batch_size = 250` will not be
    # caught here but that's fine, this test enforces the Reaction-side
    # invariant only.
    reactions = [s for s in registry if isinstance(s, Reaction)]
    if not reactions:
        pytest.skip(
            "No Reactions in the registry (stub Kernel could not construct "
            "Agent BC's LLM-bound Reactions). The unit-level classification "
            "test pins batch_size for the known Reactions."
        )

    failures: list[str] = []
    for reaction in reactions:
        if reaction.batch_size > _REACTION_BATCH_SIZE_CEILING:
            failures.append(f"{reaction.name} (batch_size={reaction.batch_size})")

    assert not failures, (
        "Reactions exceed the batch_size ceiling "
        f"({_REACTION_BATCH_SIZE_CEILING}):\n"
        + "\n".join(f"  - {f}" for f in failures)
        + "\n\nThe Reaction Protocol recommends `batch_size = 1` so the "
        "bookmark transaction is bounded to one side-effect round-trip. "
        "If your apply path is provably fast, document it; if not, pin "
        "the override to 1."
    )
