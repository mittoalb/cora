"""End-to-end MCP+bearer-auth contract tests.

Boot the app with `IDENTITY_PROVIDERS` set so bearer-auth posture
is on. Monkeypatch `build_kernel` to install a stub TokenVerifier
that accepts any bearer token and returns a fixed VerifiedPrincipal
(matching the HTTP contract-test pattern in
`test_bearer_auth_endpoints.py`).

The tests pin the full MCP edge-auth invariants end-to-end:
  - No bearer + bearer-auth mode → McpUnauthenticatedError via
    JSON-RPC isError envelope.
  - Valid bearer → tools/call succeeds AND the persisted event's
    principal_id is the BEARER-verified principal (not SYSTEM).
  - Audience binding: middleware passes SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID
    to the verifier on /mcp requests (distinct from HTTP).
  - tools/list under bearer-auth requires bearer (parity with REST
    metadata endpoints).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false

import asyncio
import json
from dataclasses import replace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from cora.api.main import create_app
from tests.contract._mcp_helpers import open_session, parse_sse_data

_IDPS_JSON = json.dumps(
    [
        {
            "issuer": "https://idp.example.com",
            "jwks_url": "http://idp.example.com/jwks.json",
            "audiences": {
                "00000000-0000-0000-0000-000000000020": "https://cora.example/http",
                "00000000-0000-0000-0000-000000000022": "https://cora.example/mcp",
            },
            "allow_insecure_jwks_url": True,
        }
    ]
)


def _install_stub_verifier(
    monkeypatch: pytest.MonkeyPatch,
    *,
    principal_id: UUID,
    audience_capture: list[UUID] | None = None,
) -> None:
    """Swap `build_kernel` so the constructed kernel has a stub
    TokenVerifier accepting any bearer token and returning a fixed
    VerifiedPrincipal. Optionally record the expected_audience
    UUIDs the middleware passes (to pin audience-per-Surface).
    """
    from cora.infrastructure import deps as deps_module
    from cora.infrastructure.ports import VerifiedPrincipal

    class _StubVerifier:
        async def verify(self, token: str, *, expected_audience: UUID) -> VerifiedPrincipal:
            _ = token
            if audience_capture is not None:
                audience_capture.append(expected_audience)
            return VerifiedPrincipal(
                principal_id=principal_id,
                subject="user-mcp",
                issuer="https://idp.example.com",
                kind="human",
            )

    original_build_kernel = deps_module.build_kernel

    async def _wrap(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        kernel, teardown = await original_build_kernel(*args, **kwargs)  # type: ignore[arg-type]
        return replace(kernel, token_verifier=_StubVerifier()), teardown

    monkeypatch.setattr(deps_module, "build_kernel", _wrap)
    monkeypatch.setattr("cora.api.main.build_kernel", _wrap)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("IDENTITY_PROVIDERS", _IDPS_JSON)


# ---------- No-bearer rejection on /mcp ----------


@pytest.mark.contract
def test_mcp_initialize_without_bearer_returns_401_under_bearer_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The MCP `initialize` request goes through `BearerAuthMiddleware`
    just like REST. Without a bearer under bearer-auth posture the
    middleware-applied `get_principal_id` would 401; the initialize
    request never reaches the FastMCP session manager. The response
    is HTTP 401 with the RFC 6750 challenge.

    Replaces an earlier `mcp_gate.py` deregistration shim with
    proper edge-time verification."""
    _install_stub_verifier(
        monkeypatch,
        principal_id=UUID("01900000-0000-7000-8000-0000000000a1"),
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "no-bearer", "version": "0.1"},
                },
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 401
    challenge = response.headers.get("WWW-Authenticate", "")
    assert challenge.startswith("Bearer ")
    assert "/.well-known/oauth-protected-resource" in challenge


# ---------- Valid-bearer happy path: principal reaches event store ----------


@pytest.mark.contract
def test_mcp_register_actor_tool_under_bearer_persists_verified_principal_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The load-bearing MCP edge-auth invariant: when an MCP tool
    call arrives with a valid bearer, the persisted event's
    `principal_id` is the BEARER-verified principal (NOT
    `SYSTEM_PRINCIPAL_ID`).

    Without this end-to-end pin, a regression that wires
    `get_mcp_principal_id` correctly but where FastMCP fails to
    propagate the Starlette `request.state` through to
    `ctx.request_context.request` would silently fall back to SYSTEM
    in mode 3 -- with no compile-time or unit-test surface to catch it."""
    verified_principal_id = UUID("01900000-0000-7000-8000-0000000000b1")
    _install_stub_verifier(monkeypatch, principal_id=verified_principal_id)

    with TestClient(create_app()) as client:
        session_headers = open_session(
            client,
            extra_headers={"Authorization": "Bearer any-token-the-stub-accepts"},
        )
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "register_actor",
                    "arguments": {"name": "BearerActor"},
                },
            },
            headers=session_headers,
        )
        assert response.status_code == 200
        body = parse_sse_data(response.text)
        assert body["result"]["isError"] is False, body
        actor_id = UUID(body["result"]["structuredContent"]["actor_id"])

        # Pin: persisted event's principal_id is the bearer-verified
        # principal, not SYSTEM, not any client-asserted value.
        deps = client.app.state.deps  # type: ignore[attr-defined]
        events, _ = asyncio.run(deps.event_store.load("Actor", actor_id))
        assert len(events) == 1
        # V2 discriminator (post PII vault); see project_pii_vault.
        assert events[0].event_type == "ActorRegisteredV2"
        assert events[0].principal_id == verified_principal_id


# ---------- Audience binding: MCP gets the MCP Surface UUID ----------


@pytest.mark.contract
def test_mcp_request_uses_mcp_surface_audience_not_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No shared `aud` across Surfaces: an /mcp/* request MUST
    cause the middleware to call `verifier.verify(token, expected_audience=
    SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID)`, NOT the HTTP Surface.

    Without this end-to-end pin, a regression in
    `_resolve_expected_audience` that routed /mcp to the HTTP Surface
    would silently accept HTTP-issued tokens on MCP (cross-surface
    token replay)."""
    from cora.infrastructure.routing import SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID

    audience_capture: list[UUID] = []
    _install_stub_verifier(
        monkeypatch,
        principal_id=UUID("01900000-0000-7000-8000-0000000000c1"),
        audience_capture=audience_capture,
    )

    with TestClient(create_app()) as client:
        open_session(
            client,
            extra_headers={"Authorization": "Bearer mcp-token"},
        )

    assert audience_capture, "Verifier was not called -- middleware skipped /mcp?"
    # Every audience seen during the MCP handshake MUST be the MCP Surface.
    for aud in audience_capture:
        assert aud == SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID, (
            f"Middleware passed audience={aud} for /mcp; expected "
            f"SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID. Audience invariant violated."
        )


# ---------- X-Principal-Id ignored under bearer-auth on MCP ----------


@pytest.mark.contract
def test_mcp_x_principal_id_header_ignored_when_bearer_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When BOTH a verified bearer AND an X-Principal-Id header are
    sent on an MCP request, the persisted event carries the BEARER's
    principal_id, not the header's. Anti-hook posture: silent-ignore of the
    legacy header under bearer-auth (mirrors HTTP)."""
    verified_principal_id = UUID("01900000-0000-7000-8000-0000000000d1")
    spoofed_principal_id = UUID("01900000-0000-7000-8000-0000000000d9")
    _install_stub_verifier(monkeypatch, principal_id=verified_principal_id)

    with TestClient(create_app()) as client:
        session_headers = open_session(
            client,
            extra_headers={
                "Authorization": "Bearer real-token",
                "X-Principal-Id": str(spoofed_principal_id),
            },
        )
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "register_actor",
                    "arguments": {"name": "NoSpoof"},
                },
            },
            headers=session_headers,
        )
        assert response.status_code == 200
        body = parse_sse_data(response.text)
        actor_id = UUID(body["result"]["structuredContent"]["actor_id"])

        deps = client.app.state.deps  # type: ignore[attr-defined]
        events, _ = asyncio.run(deps.event_store.load("Actor", actor_id))
        assert events[0].principal_id == verified_principal_id
        assert events[0].principal_id != spoofed_principal_id


# ---------- Tools/list under bearer-auth ----------


@pytest.mark.contract
def test_mcp_tools_list_under_bearer_succeeds_with_valid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """tools/list is metadata-only but still goes through the bearer
    middleware (parity with REST metadata endpoints like /openapi.json).
    With a valid bearer it succeeds and lists every registered tool."""
    _install_stub_verifier(
        monkeypatch,
        principal_id=UUID("01900000-0000-7000-8000-0000000000e1"),
    )

    with TestClient(create_app()) as client:
        session_headers = open_session(
            client,
            extra_headers={"Authorization": "Bearer good"},
        )
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )

    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tools = body["result"]["tools"]

    # Every tool registered in main.py should appear, including writes.
    tool_names = {t["name"] for t in tools}
    assert "register_actor" in tool_names
    assert "get_actor" in tool_names
    assert "register_subject" in tool_names


# ---------- Tools/list under bearer-auth without bearer ----------


@pytest.mark.contract
def test_mcp_tools_list_without_bearer_under_bearer_auth_returns_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mirror to test_mcp_initialize_without_bearer_returns_401:
    every /mcp request needs a bearer under bearer-auth posture,
    INCLUDING the metadata-only tools/list endpoint."""
    _install_stub_verifier(
        monkeypatch,
        principal_id=UUID("01900000-0000-7000-8000-0000000000f1"),
    )

    with TestClient(create_app()) as client:
        # initialize without bearer 401s before we can even reach tools/list.
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "no-bearer", "version": "0.1"},
                },
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 401


# ---------- gap closures (gate-review test-axis MEDIUM 1, 4, 5) ----------


@pytest.mark.contract
def test_mcp_notifications_initialized_without_bearer_returns_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closes the test-axis MEDIUM 1 gap. `notifications/initialized`
    is one of the FastMCP framing methods explicitly cited in
    `bearer_middleware.py:dispatch` as the reason for middleware-side
    enforcement of bearer-required on `/mcp/*` (Decision 8). Without this
    contract test, a regression that special-cased notifications back to
    the no-Auth pass-through path would slip past the unit + initialize
    contract tests.
    """
    _install_stub_verifier(
        monkeypatch,
        principal_id=UUID("01900000-0000-7000-8000-0000000000f2"),
    )

    with TestClient(create_app()) as client:
        # Open a session with bearer so we have a session id; then drop the
        # bearer on the follow-up notification.
        session_headers = open_session(
            client,
            extra_headers={"Authorization": "Bearer good"},
        )
        bare = {k: v for k, v in session_headers.items() if k != "Authorization"}
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=bare,
        )

    assert response.status_code == 401
    challenge = response.headers.get("WWW-Authenticate", "")
    assert challenge.startswith("Bearer ")


@pytest.mark.contract
def test_mcp_tools_list_under_legacy_mode_lists_every_write_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closes the test-axis MEDIUM 4 gap. Previously the `mcp_gate.py`
    shim deregistered write tools under prod posture; that shim is
    deleted. In LEGACY mode (no IDENTITY_PROVIDERS) the bearer
    middleware short-circuits and `get_mcp_principal_id(ctx)` falls
    through to SYSTEM, so write tools must remain registered. Pin
    parity-across-modes so a regression that re-introduces conditional
    deregistration in legacy mode would surface here.
    """
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("IDENTITY_PROVIDERS", raising=False)

    with TestClient(create_app()) as client:
        session_headers = open_session(client)
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=session_headers,
        )

    assert response.status_code == 200
    body = parse_sse_data(response.text)
    tool_names = {t["name"] for t in body["result"]["tools"]}
    # Sample of write tools across multiple BCs. Each must be present
    # under legacy mode just as it is under bearer-auth mode.
    for write_tool in ("register_actor", "register_subject", "define_calibration"):
        assert write_tool in tool_names, (
            f"Write tool {write_tool!r} missing from tools/list under legacy mode; "
            "mcp_gate deletion regression?"
        )


@pytest.mark.contract
def test_mcp_invalid_token_on_tools_call_returns_401_with_challenge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closes the test-axis MEDIUM 5 gap. A bearer that fails
    verification on `/mcp/*` MUST return 401 with the RFC 6750
    `WWW-Authenticate: Bearer error="<reason>"` challenge at parity
    with HTTP behavior. The unit-tier test_mcp_path_invalid_token_returns_401
    covers the Starlette layer; this pins the same shape end-to-end
    through the full FastAPI mount + FastMCP routing.
    """
    from cora.infrastructure import deps as deps_module
    from cora.infrastructure.ports import InvalidTokenError, VerifiedPrincipal

    _ = VerifiedPrincipal

    class _AlwaysInvalid:
        async def verify(self, token: str, *, expected_audience: UUID):  # type: ignore[no-untyped-def]
            _ = token, expected_audience
            raise InvalidTokenError("bad_signature", "stub denied")

    original = deps_module.build_kernel

    async def _wrap(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        from dataclasses import replace

        kernel, teardown = await original(*args, **kwargs)  # type: ignore[arg-type]
        return replace(kernel, token_verifier=_AlwaysInvalid()), teardown

    monkeypatch.setattr(deps_module, "build_kernel", _wrap)
    monkeypatch.setattr("cora.api.main.build_kernel", _wrap)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("IDENTITY_PROVIDERS", _IDPS_JSON)

    with TestClient(create_app()) as client:
        # Send a bearer; the stub rejects it.
        response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "invalid-bearer", "version": "0.1"},
                },
            },
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "Authorization": "Bearer this-will-be-rejected",
            },
        )

    assert response.status_code == 401
    challenge = response.headers.get("WWW-Authenticate", "")
    assert challenge.startswith("Bearer ")
    assert 'error="bad_signature"' in challenge
