"""Contract tests for `POST /agents/run_debriefer/invoke`."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.agent.features.re_debrief_run.route import (
    _get_handler as _get_re_debrief_handler,  # pyright: ignore[reportPrivateUsage]
)
from cora.api.main import create_app
from cora.infrastructure.ports import FakeLLMAdapter, FakeLLMResponse

_CANNED_OK = FakeLLMResponse(
    parsed={
        "choice": "NominalCompletion",
        "confidence": 0.9,
        "reasoning": (
            "On-demand re-debrief contract test. Synopsis: a single-Plan "
            "tomography Run on the bound Subject ran to RunCompleted. "
            "What was supposed to happen: standard scan execution. What "
            "actually happened: clean termination with no adjustments. "
            "Why the difference: no difference; operator re-triggered."
        ),
    },
    stop_reason="tool_use",
    model_id="claude-haiku-4-5",
)


@pytest.mark.contract
def test_post_invoke_returns_503_when_kernel_llm_unwired() -> None:
    """Default app_env=test wires `kernel.llm=None`; the route's
    `_get_handler` short-circuits to 503 before reaching the
    Idempotency-Key middleware."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/agents/run_debriefer/invoke",
            json={"run_id": "01900000-0000-7000-8000-000000000001"},
        )
    assert response.status_code == 503, response.text
    assert "kernel.llm" in response.json()["detail"]


@pytest.mark.contract
def test_post_invoke_returns_422_on_missing_run_id_when_handler_wired() -> None:
    """Pydantic body validation: required `run_id` missing -> 422.

    The route's `_get_handler` Depends runs BEFORE Pydantic body
    validation in FastAPI, so the default app_env=test path (no LLM)
    short-circuits to 503 regardless of body. Override to a fake
    handler so the 503 path doesn't preempt the 422 path."""
    app = create_app()
    app.dependency_overrides[_get_re_debrief_handler] = lambda: _stub_handler_never_called

    with TestClient(app) as client:
        response = client.post(
            "/agents/run_debriefer/invoke",
            json={},
        )
    assert response.status_code == 422, response.text


@pytest.mark.contract
def test_post_invoke_returns_422_on_malformed_run_id_when_handler_wired() -> None:
    app = create_app()
    app.dependency_overrides[_get_re_debrief_handler] = lambda: _stub_handler_never_called

    with TestClient(app) as client:
        response = client.post(
            "/agents/run_debriefer/invoke",
            json={"run_id": "not-a-uuid"},
        )
    assert response.status_code == 422, response.text


async def _stub_handler_never_called(*args: Any, **kwargs: Any) -> UUID:
    """Test handler that should never be called -- if it is, Pydantic
    body validation didn't fire first (which is the bug we're guarding
    against)."""
    _ = (args, kwargs)
    msg = "stub handler called despite body validation failure"
    raise AssertionError(msg)


@pytest.mark.contract
def test_post_invoke_dependency_injection_path_overrides_handler() -> None:
    """Sanity-check FastAPI's `dependency_overrides` works against
    the route's `_get_handler` for tests that bypass the lifespan."""
    app = create_app()

    class _FakeHandler:
        def __init__(self) -> None:
            self.calls: list[tuple[Any, Any]] = []

        async def __call__(self, *args: Any, **kwargs: Any) -> UUID:
            self.calls.append((args, kwargs))
            return UUID("01900000-0000-7000-8000-00000000fc99")

    fake = _FakeHandler()
    app.dependency_overrides[_get_re_debrief_handler] = lambda: fake  # type: ignore[arg-type]

    with TestClient(app) as client:
        response = client.post(
            "/agents/run_debriefer/invoke",
            json={"run_id": "01900000-0000-7000-8000-000000000001"},
        )
    assert response.status_code == 201, response.text
    assert response.json()["decision_id"] == "01900000-0000-7000-8000-00000000fc99"
    assert len(fake.calls) == 1


@pytest.mark.contract
def test_post_invoke_propagates_idempotency_key_header() -> None:
    """The route reads `Idempotency-Key` header and forwards it as
    a handler kwarg (per the Brandur envelope wired in wire.py)."""
    app = create_app()

    captured_kwargs: dict[str, Any] = {}

    async def _fake_handler(*args: Any, **kwargs: Any) -> UUID:
        _ = args
        captured_kwargs.update(kwargs)
        return UUID("01900000-0000-7000-8000-00000000fc88")

    app.dependency_overrides[_get_re_debrief_handler] = lambda: _fake_handler  # type: ignore[arg-type]

    with TestClient(app) as client:
        response = client.post(
            "/agents/run_debriefer/invoke",
            json={"run_id": "01900000-0000-7000-8000-000000000001"},
            headers={"Idempotency-Key": "test-redebrief-key-001"},
        )
    assert response.status_code == 201, response.text
    assert captured_kwargs.get("idempotency_key") == "test-redebrief-key-001"


# ---------- Cleanup-pass additions (test-coverage gate-review P1s) ----------


@pytest.mark.contract
def test_post_invoke_returns_403_when_authz_denies() -> None:
    """Closes test-coverage P1 #1: handler-level UnauthorizedError test
    exists, but no contract test pinned the REST 403 mapping for the
    new slice's authz-deny path. The shared `_handle_unauthorized`
    handler registered in `routes.py` should map it."""
    from cora.agent.errors import UnauthorizedError

    app = create_app()

    async def _denying_handler(*args: Any, **kwargs: Any) -> UUID:
        _ = (args, kwargs)
        raise UnauthorizedError("test denial")

    app.dependency_overrides[_get_re_debrief_handler] = lambda: _denying_handler  # type: ignore[arg-type]

    with TestClient(app) as client:
        response = client.post(
            "/agents/run_debriefer/invoke",
            json={"run_id": "01900000-0000-7000-8000-000000000001"},
        )
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "test denial"


@pytest.mark.parametrize(
    ("exc_factory", "expected_status"),
    [
        # Cross-aggregate guards: all 400.
        pytest.param(
            lambda: _agent_not_seeded_error(),
            400,
            id="AgentNotSeededError",
        ),
        pytest.param(
            lambda: _agent_deactivated_error(),
            400,
            id="AgentDeactivatedError",
        ),
        pytest.param(
            lambda: _parent_decision_agent_mismatch_error(),
            400,
            id="ParentDecisionAgentMismatchError",
        ),
        pytest.param(
            lambda: _parent_decision_run_mismatch_error(),
            400,
            id="ParentDecisionRunMismatchError",
        ),
        # Cross-BC owned mappings: RunNotFoundError -> 404 (Run BC),
        # ParentDecisionMissingError -> 409 (Decision BC). Confirm
        # they flow through the agent's route too.
        pytest.param(
            lambda: _run_not_found_error(),
            404,
            id="RunNotFoundError",
        ),
        pytest.param(
            lambda: _parent_decision_missing_error(),
            409,
            id="ParentDecisionMissingError",
        ),
    ],
)
@pytest.mark.contract
def test_post_invoke_exception_to_status_mapping(
    exc_factory: Any,
    expected_status: int,
) -> None:
    """Closes test-coverage P1 #2: every cross-aggregate guard's HTTP
    mapping is pinned via parametrized contract test. A single
    registration-loop typo in routes.py would silently surface as 500
    in production without this guard."""
    app = create_app()

    async def _raising_handler(*args: Any, **kwargs: Any) -> UUID:
        _ = (args, kwargs)
        raise exc_factory()

    app.dependency_overrides[_get_re_debrief_handler] = lambda: _raising_handler  # type: ignore[arg-type]

    with TestClient(app) as client:
        response = client.post(
            "/agents/run_debriefer/invoke",
            json={"run_id": "01900000-0000-7000-8000-000000000001"},
        )
    assert response.status_code == expected_status, response.text


def _agent_not_seeded_error() -> Exception:
    from cora.agent.aggregates.agent import AgentNotSeededError

    return AgentNotSeededError(UUID("01900000-0000-7000-8000-0000aaaa0010"), "RunDebrief")


def _agent_deactivated_error() -> Exception:
    from cora.agent.aggregates.agent import AgentDeactivatedError

    return AgentDeactivatedError(UUID("01900000-0000-7000-8000-0000aaaa0010"))


def _parent_decision_agent_mismatch_error() -> Exception:
    from cora.decision.aggregates.decision import ParentDecisionAgentMismatchError

    return ParentDecisionAgentMismatchError(
        UUID("01900000-0000-7000-8000-00000000fc01"), "OtherAgent"
    )


def _parent_decision_run_mismatch_error() -> Exception:
    from cora.decision.aggregates.decision import ParentDecisionRunMismatchError

    return ParentDecisionRunMismatchError(
        UUID("01900000-0000-7000-8000-00000000fc01"),
        UUID("01900000-0000-7000-8000-00000000aaaa"),
    )


def _run_not_found_error() -> Exception:
    from cora.run.aggregates.run import RunNotFoundError

    return RunNotFoundError(UUID("01900000-0000-7000-8000-000000000001"))


def _parent_decision_missing_error() -> Exception:
    from cora.decision.aggregates.decision import ParentDecisionMissingError

    return ParentDecisionMissingError(UUID("01900000-0000-7000-8000-00000000fc01"))


# Pin the FakeLLMAdapter reference + canned response so the import isn't
# tree-shaken; they're load-bearing for the pilot real-Anthropic transition,
# when an integration test will swap _CANNED_OK with a recorded cassette.
_ = (FakeLLMAdapter, _CANNED_OK)
