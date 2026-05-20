"""Unit tests for register_agent_subscribers (Phase 8f-b iter 2b)."""

# pyright: reportUnknownMemberType=false

from datetime import UTC, datetime

import pytest

from cora.agent import register_agent_subscribers
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    FakeClock,
    FakeLLMAdapter,
    FixedIdGenerator,
)
from cora.infrastructure.projection.registry import ProjectionRegistry


def _kernel(*, llm: object | None) -> object:
    settings = Settings()  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)),
        id_generator=FixedIdGenerator([]),
        authz=AllowAllAuthorize(),
        llm=llm,  # type: ignore[arg-type]
    )


@pytest.mark.unit
def test_registers_run_debrief_when_llm_configured() -> None:
    registry = ProjectionRegistry()
    kernel = _kernel(llm=FakeLLMAdapter())

    register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]

    assert "run_debrief" in registry.names()


@pytest.mark.unit
def test_skips_run_debrief_when_llm_is_none() -> None:
    """If ANTHROPIC_API_KEY is unset, the subscriber would crash on
    every apply() (no LLM to call). Skip registration cleanly with
    a warning rather than crash at app boot."""
    registry = ProjectionRegistry()
    kernel = _kernel(llm=None)

    register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]

    assert "run_debrief" not in registry.names()


@pytest.mark.unit
def test_registration_is_idempotent_safe_for_one_registry() -> None:
    """Double-registration of the same registry would raise
    DuplicateProjectionError on the second call (the framework's
    invariant). Pin that we register only ONCE."""
    registry = ProjectionRegistry()
    kernel = _kernel(llm=FakeLLMAdapter())
    register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]

    # Second call should raise (registry already has the subscriber).
    from cora.infrastructure.projection.registry import DuplicateProjectionError

    with pytest.raises(DuplicateProjectionError):
        register_agent_subscribers(registry, kernel)  # type: ignore[arg-type]
