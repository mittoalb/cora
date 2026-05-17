"""Agent BC's `LLMPortFactory` for the composition root.

Phase 8f-b iter 2a. Bound from `cora.api.main` into `build_kernel`
the same way `cora.trust.authorize_factory.build_authorize` is
bound. Lives in Agent BC because the production implementor
(`AnthropicLLMAdapter`) lives here too (cross-BC adapter-ownership
convention; Safety BC owns `PostgresClearanceLookup`, Caution BC
owns `PostgresCautionLookup`).

When `Settings.anthropic_api_key` is unset, returns `None` so the
Kernel ends up with `llm=None` and Agent subscribers fail-fast at
registration. This is intentional: a misconfigured prod deployment
should not silently downgrade to a no-LLM mode where RunDebrief
goes silent. Iter 2b's subscriber-registration step adds the
fail-fast on `kernel.llm is None`.
"""

from cora.agent.adapters.anthropic_llm_adapter import AnthropicLLMAdapter
from cora.infrastructure.config import Settings
from cora.infrastructure.ports import LLMPort


def build_llm(settings: Settings) -> LLMPort | None:
    """Construct the production LLMPort or return `None` when unconfigured.

    Today this branches on `settings.anthropic_api_key`; a future
    multi-provider deployment would branch on a `settings.llm_provider`
    field with `anthropic` as one variant.

    `SecretStr.get_secret_value()` is the ONLY place in the codebase
    that unwraps the API key; passing the raw string to the adapter
    constructor is the boundary at which "secret material" becomes
    "live credential". Adapter scope is responsible for not re-
    exposing it (eg. via `repr(adapter)` or `str(adapter._client)`).
    """
    if settings.anthropic_api_key is None:
        return None
    return AnthropicLLMAdapter(api_key=settings.anthropic_api_key.get_secret_value())


__all__ = ["build_llm"]
