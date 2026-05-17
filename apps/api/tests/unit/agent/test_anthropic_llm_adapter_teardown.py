"""Unit tests for AnthropicLLMAdapter.aclose() teardown (Phase 8f-b iter 2b).

The adapter exposes `aclose()` so the Kernel's teardown chain can
release the underlying httpx connection pool at shutdown. Without
this, the SDK leaks its pool on every process exit (iter 2a
test-coverage P1 watch item; iter 2b closes it).
"""

# pyright: reportUnknownMemberType=false, reportPrivateUsage=false

from typing import Any
from unittest.mock import AsyncMock

import pytest

from cora.agent.adapters import AnthropicLLMAdapter


@pytest.mark.unit
async def test_aclose_invokes_sdk_client_close() -> None:
    """Adapter delegates to AsyncAnthropic.close() so the httpx
    connection pool is released."""
    mock_client: Any = AsyncMock()
    adapter = AnthropicLLMAdapter(api_key="sk-test", client=mock_client)

    await adapter.aclose()

    mock_client.close.assert_awaited_once()


@pytest.mark.unit
async def test_kernel_teardown_calls_llm_aclose() -> None:
    """When `kernel.llm` is the production AnthropicLLMAdapter,
    `build_kernel`'s composed teardown invokes `aclose()` so the
    httpx pool releases at FastAPI shutdown."""
    from cora.infrastructure.deps import _maybe_llm_teardown

    mock_client: Any = AsyncMock()
    adapter = AnthropicLLMAdapter(api_key="sk-test", client=mock_client)
    teardown = _maybe_llm_teardown(adapter)

    await teardown()

    mock_client.close.assert_awaited_once()


@pytest.mark.unit
async def test_kernel_teardown_no_op_when_llm_is_none() -> None:
    """No LLM configured -> teardown is a clean no-op."""
    from cora.infrastructure.deps import _maybe_llm_teardown

    teardown = _maybe_llm_teardown(None)
    # Must not raise.
    await teardown()


@pytest.mark.unit
async def test_kernel_teardown_no_op_for_adapter_without_aclose() -> None:
    """`FakeLLMAdapter` (and any other LLMPort impl without an
    `aclose` method) skips the close step cleanly."""
    from cora.infrastructure.deps import _maybe_llm_teardown
    from cora.infrastructure.ports import FakeLLMAdapter

    fake = FakeLLMAdapter()
    teardown = _maybe_llm_teardown(fake)
    # Must not raise (FakeLLMAdapter has no aclose method).
    await teardown()


@pytest.mark.unit
async def test_compose_teardowns_runs_all_in_order() -> None:
    """The composed teardown chains LLM close + pool close. Order is
    preserved and both run even if one raises (the first exception
    is the one re-raised after all teardowns attempt)."""
    from cora.infrastructure.deps import _compose_teardowns

    calls: list[str] = []

    async def first() -> None:
        calls.append("first")

    async def second() -> None:
        calls.append("second")

    async def third() -> None:
        calls.append("third")

    await _compose_teardowns([first, second, third])()

    assert calls == ["first", "second", "third"]


@pytest.mark.unit
async def test_compose_teardowns_continues_past_a_raise() -> None:
    """If teardown N raises, teardowns N+1, N+2 still run; the
    first raised exception is re-raised at the end."""
    from cora.infrastructure.deps import _compose_teardowns

    calls: list[str] = []

    async def first() -> None:
        calls.append("first")
        raise RuntimeError("boom in first")

    async def second() -> None:
        calls.append("second")

    async def third() -> None:
        calls.append("third")

    with pytest.raises(RuntimeError, match="boom in first"):
        await _compose_teardowns([first, second, third])()

    # All three teardowns ran (no early exit on the first raise).
    assert calls == ["first", "second", "third"]
