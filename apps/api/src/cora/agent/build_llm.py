"""Agent BC's `LLMFactory` for the composition root.

Bound from `cora.api.main` into `build_kernel` the same way
`cora.trust.build_authorize.build_authorize` is bound. Lives in
Agent BC because the production implementor (`AnthropicLLM`)
lives here too (cross-BC adapter-ownership convention; Safety BC
owns `PostgresClearanceLookup`, Caution BC owns
`PostgresCautionLookup`).

When `Settings.anthropic_api_key` is unset, returns `None` so the
Kernel ends up with `llm=None` and Agent subscribers fail-fast at
registration. This is intentional: a misconfigured prod deployment
should not silently downgrade to a no-LLM mode where RunDebriefer
goes silent. The subscriber-registration step fail-fasts on
`kernel.llm is None`.
"""

from cora.agent.adapters.anthropic_llm import AnthropicLLM
from cora.infrastructure.config import Settings
from cora.infrastructure.ports import LLM


def build_llm(settings: Settings) -> LLM | None:
    """Construct the production LLM or return `None` when unconfigured.

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
    return AnthropicLLM(api_key=settings.anthropic_api_key.get_secret_value())


__all__ = ["build_llm"]
