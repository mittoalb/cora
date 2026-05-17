"""Unit tests for the `build_kernel` wiring.

Verifies the `app_env` branching: `test` selects the in-memory store and
a no-op teardown; the production branch is exercised by integration tests
that have a real Postgres available.

Also covers the Authorize-adapter selection driven by
`Settings.trust_policy_id`: unset -> AllowAllAuthorize; set ->
TrustAuthorize. The factory is injected by the composition root
(see `cora.api.main`); tests inject `build_authorize` directly to
exercise the production wiring without going through FastAPI.
"""

from uuid import UUID

import pytest

from cora.agent import build_llm
from cora.agent.adapters import AnthropicLLMAdapter
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import build_kernel
from cora.infrastructure.memory.event_store import InMemoryEventStore
from cora.infrastructure.memory.idempotency import InMemoryIdempotencyStore
from cora.infrastructure.ports import AllowAllAuthorize, FakeLLMAdapter
from cora.trust import build_authorize
from cora.trust.authorize import TrustAuthorize


@pytest.mark.unit
async def test_build_kernel_uses_in_memory_stores_in_test_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")

    deps, teardown = await build_kernel(authorize_factory=build_authorize)

    assert deps.settings.app_env == "test"
    assert isinstance(deps.event_store, InMemoryEventStore)
    assert isinstance(deps.idempotency_store, InMemoryIdempotencyStore)
    # Teardown is a no-op in test mode but must still be awaitable.
    await teardown()


@pytest.mark.unit
async def test_build_kernel_populates_all_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every BC's wiring relies on these fields being present and non-None."""
    monkeypatch.setenv("APP_ENV", "test")

    deps, teardown = await build_kernel(authorize_factory=build_authorize)

    assert deps.clock is not None
    assert deps.id_generator is not None
    assert deps.authorize is not None
    assert deps.event_store is not None
    assert deps.idempotency_store is not None
    await teardown()


@pytest.mark.unit
async def test_build_kernel_uses_allow_all_authorize_when_no_policy_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 1 permissive default: no `trust_policy_id` -> no real auth.
    Tests + dev environments rely on this; flipping it to fail-closed
    would be a significant behavior change."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("TRUST_POLICY_ID", raising=False)

    deps, teardown = await build_kernel(authorize_factory=build_authorize)
    assert isinstance(deps.authorize, AllowAllAuthorize)
    await teardown()


@pytest.mark.unit
async def test_build_kernel_uses_trust_authorize_when_policy_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting `trust_policy_id` swaps to the real Trust adapter.
    The adapter loads the configured policy at request time; this test
    verifies the WIRING, not the gating semantics (those live in
    `tests/unit/trust/test_trust_authorize.py`)."""
    monkeypatch.setenv("APP_ENV", "test")
    policy_id = UUID("01900000-0000-7000-8000-000000000601")
    monkeypatch.setenv("TRUST_POLICY_ID", str(policy_id))

    deps, teardown = await build_kernel(authorize_factory=build_authorize)
    assert isinstance(deps.authorize, TrustAuthorize)
    await teardown()


# ---------- Phase 8f-b iter 2a: LLM + LogbookMirror wiring ----------


@pytest.mark.unit
async def test_kernel_llm_is_none_by_default_in_test_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`build_kernel` in `app_env=test` does NOT call llm_factory;
    Agent subscribers fail-fast on `kernel.llm is None` at iter 2b
    registration. Defaulting to None in tests keeps the contract
    explicit: opt-in to LLM by passing FakeLLMAdapter to
    make_inmemory_kernel."""
    monkeypatch.setenv("APP_ENV", "test")
    deps, teardown = await build_kernel(authorize_factory=build_authorize, llm_factory=build_llm)
    assert deps.llm is None
    await teardown()


@pytest.mark.unit
async def test_kernel_logbook_mirror_is_none_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No production implementor lands at 8f-b; the field reserves
    the slot and subscribers short-circuit on `is None`."""
    monkeypatch.setenv("APP_ENV", "test")
    deps, teardown = await build_kernel(authorize_factory=build_authorize)
    assert deps.logbook_mirror is None
    await teardown()


@pytest.mark.unit
def test_build_llm_returns_none_when_api_key_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agent BC's LLMPortFactory short-circuits cleanly when no
    credential is configured; subscriber registration handles the
    fail-fast at iter 2b."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = Settings()  # type: ignore[call-arg]
    assert build_llm(settings) is None


@pytest.mark.unit
def test_build_llm_returns_anthropic_adapter_when_api_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the operator wires ANTHROPIC_API_KEY, the production
    AnthropicLLMAdapter lands in the Kernel."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
    settings = Settings()  # type: ignore[call-arg]
    llm = build_llm(settings)
    assert isinstance(llm, AnthropicLLMAdapter)


@pytest.mark.unit
def test_anthropic_api_key_is_secret_str_and_redacted_in_repr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closes gate-review architecture P1 #2 (secret leak in
    repr/str/json). `SecretStr` redacts the raw value to `**********`
    in every standard serialisation path; the raw key surfaces only
    via `.get_secret_value()`, which only `build_llm` calls."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-VALUE-12345")
    settings = Settings()  # type: ignore[call-arg]
    assert settings.anthropic_api_key is not None
    # `repr(SecretStr)` redacts.
    assert "sk-ant-secret-VALUE-12345" not in repr(settings)
    assert "sk-ant-secret-VALUE-12345" not in repr(settings.anthropic_api_key)
    # `str(SecretStr)` redacts.
    assert "sk-ant-secret-VALUE-12345" not in str(settings.anthropic_api_key)
    # `model_dump_json()` redacts.
    assert "sk-ant-secret-VALUE-12345" not in settings.model_dump_json()
    # Round-trip via `.get_secret_value()` works (the legitimate read path).
    assert settings.anthropic_api_key.get_secret_value() == "sk-ant-secret-VALUE-12345"


@pytest.mark.unit
async def test_make_inmemory_kernel_accepts_fake_llm_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Subscriber-level tests that need an LLM inject FakeLLMAdapter
    via make_inmemory_kernel(..., llm=...). Pins the override seam."""
    from cora.infrastructure.deps import make_inmemory_kernel
    from cora.infrastructure.ports import SystemClock, UUIDv7Generator

    fake = FakeLLMAdapter()
    settings = Settings()  # type: ignore[call-arg]
    kernel = make_inmemory_kernel(
        settings=settings,
        clock=SystemClock(),
        id_generator=UUIDv7Generator(),
        authorize=AllowAllAuthorize(),
        llm=fake,
    )
    assert kernel.llm is fake
