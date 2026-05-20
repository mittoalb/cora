"""Unit tests for the LLM value types + FakeLLMAdapter (Phase 8f-b iter 2a).

Pins the port-level contract that subscriber tests at iter 2b will
rely on (queue semantics, error pass-through, request capture).
"""

import pytest

from cora.infrastructure.ports.llm import (
    CacheBreakpoint,
    FakeLLMAdapter,
    FakeLLMExhaustedError,
    FakeLLMResponse,
    LLMAuthenticationError,
    LLMChatRequest,
    LLMContentBlock,
    LLMError,
    LLMInvalidRequestError,
    LLMRateLimitError,
    LLMResponse,
    LLMSchemaValidationError,
    LLMServerError,
    LLMSystemPrompt,
    LLMTimeoutError,
    LLMUsage,
    ModelRef,
)


def _request() -> LLMChatRequest:
    return LLMChatRequest(
        system=LLMSystemPrompt(blocks=(LLMContentBlock(text="be helpful"),)),
        user_message=LLMContentBlock(text="hi"),
        structured_output_schema={"type": "object"},
        model_ref=ModelRef(provider="anthropic", model="claude-haiku-4-5"),
    )


@pytest.mark.unit
def test_modelref_snapshot_pin_defaults_none() -> None:
    ref = ModelRef(provider="anthropic", model="claude-opus-4-7")
    assert ref.snapshot_pin is None


@pytest.mark.unit
def test_cache_breakpoint_default_ttl_is_5m() -> None:
    bp = CacheBreakpoint()
    assert bp.ttl == "5m"


@pytest.mark.unit
def test_cache_breakpoint_1h_value() -> None:
    assert CacheBreakpoint(ttl="1h").ttl == "1h"


@pytest.mark.unit
def test_llm_usage_cache_fields_default_zero() -> None:
    """Providers that don't report cache stats should coerce to 0."""
    usage = LLMUsage(input_tokens=10, output_tokens=20)
    assert usage.cache_creation_input_tokens == 0
    assert usage.cache_read_input_tokens == 0


@pytest.mark.unit
def test_llm_error_subclasses_inherit_from_base() -> None:
    """isinstance(specific, LLMError) is load-bearing for iter 2b
    retry logic that catches the base class."""
    for cls in (
        LLMRateLimitError,
        LLMServerError,
        LLMTimeoutError,
        LLMAuthenticationError,
        LLMInvalidRequestError,
        LLMSchemaValidationError,
        FakeLLMExhaustedError,
    ):
        assert issubclass(cls, LLMError), cls.__name__


@pytest.mark.unit
async def test_fake_returns_canned_response() -> None:
    adapter = FakeLLMAdapter(responses=[FakeLLMResponse(parsed={"choice": "NominalCompletion"})])
    result = await adapter.chat(_request())
    assert isinstance(result, LLMResponse)
    assert result.parsed == {"choice": "NominalCompletion"}
    assert result.stop_reason == "end_turn"  # default
    assert result.model_id == "fake-model-v1"  # default


@pytest.mark.unit
async def test_fake_captures_received_request_in_order() -> None:
    adapter = FakeLLMAdapter(
        responses=[
            FakeLLMResponse(parsed={"i": 0}),
            FakeLLMResponse(parsed={"i": 1}),
        ]
    )
    req0 = _request()
    req1 = LLMChatRequest(
        system=LLMSystemPrompt(blocks=(LLMContentBlock(text="other"),)),
        user_message=LLMContentBlock(text="bye"),
        structured_output_schema={"type": "object"},
        model_ref=ModelRef(provider="anthropic", model="claude-haiku-4-5"),
    )
    await adapter.chat(req0)
    await adapter.chat(req1)
    assert adapter.received == [req0, req1]


@pytest.mark.unit
async def test_fake_exhausted_raises() -> None:
    adapter = FakeLLMAdapter(responses=[])
    with pytest.raises(FakeLLMExhaustedError, match="queue exhausted"):
        await adapter.chat(_request())


@pytest.mark.unit
async def test_fake_passes_through_enqueued_errors() -> None:
    """Operators can enqueue an LLMError instance to simulate a
    failure on the Nth call without monkeypatching."""
    adapter = FakeLLMAdapter(
        responses=[
            FakeLLMResponse(parsed={"ok": True}),
            LLMRateLimitError("synthetic 429"),
        ]
    )
    await adapter.chat(_request())  # ok
    with pytest.raises(LLMRateLimitError, match="synthetic 429"):
        await adapter.chat(_request())


@pytest.mark.unit
async def test_fake_enqueue_appends_to_queue() -> None:
    adapter = FakeLLMAdapter()
    adapter.enqueue(FakeLLMResponse(parsed={"a": 1}))
    adapter.enqueue(FakeLLMResponse(parsed={"a": 2}))
    r1 = await adapter.chat(_request())
    r2 = await adapter.chat(_request())
    assert r1.parsed == {"a": 1}
    assert r2.parsed == {"a": 2}


@pytest.mark.unit
async def test_fake_usage_round_trips() -> None:
    """Usage on the canned response flows through to the LLMResponse."""
    adapter = FakeLLMAdapter(
        responses=[
            FakeLLMResponse(
                parsed={},
                usage=LLMUsage(
                    input_tokens=100,
                    output_tokens=50,
                    cache_creation_input_tokens=4000,
                    cache_read_input_tokens=1000,
                ),
            )
        ]
    )
    result = await adapter.chat(_request())
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 50
    assert result.usage.cache_creation_input_tokens == 4000
    assert result.usage.cache_read_input_tokens == 1000


@pytest.mark.unit
async def test_fake_stop_reason_and_model_id_round_trip() -> None:
    adapter = FakeLLMAdapter(
        responses=[
            FakeLLMResponse(
                parsed={},
                stop_reason="max_tokens",
                model_id="claude-opus-4-7-20260301",
            )
        ]
    )
    result = await adapter.chat(_request())
    assert result.stop_reason == "max_tokens"
    assert result.model_id == "claude-opus-4-7-20260301"
