"""Architecture fitness functions for MCP edge-auth invariants.

Mirrors the HTTP `test_edge_auth_invariants.py` shape (4 invariants
provable from the import graph + AST) for the MCP side of the auth
parity. Every hardcoded `SYSTEM_PRINCIPAL_ID` in MCP tool handlers
has been replaced with a `get_mcp_principal_id(ctx)` call; these
fitnesses keep that swap permanent by catching any future
regression at PR time:

  1. **No SYSTEM_PRINCIPAL_ID in `principal_id=` kwargs of MCP tools.**
     A new tool that copy-paste-defaults to SYSTEM bypasses the
     bearer-auth contract entirely. The AST walk picks the keyword
     arg by name.

  2. **Every MCP tool function takes a `ctx: Context` parameter.**
     FastMCP injects Context based on type annotation; a tool that
     forgets it cannot call `get_mcp_principal_id(ctx)` at all and
     would have to either (a) hardcode SYSTEM again (caught by #1)
     or (b) leave the principal_id off the handler call entirely
     (which would fail type-checking, but this fitness is the
     primary surface).

  3. **`get_mcp_principal_id` signature pin.** A typo or kwarg rename
     in the resolver would silently break every tool's principal
     extraction at runtime; the signature pin catches it at import
     time.

  4. **`BearerAuthMiddleware` covers `/mcp/*` paths.** The earlier
     `/mcp/*` skip is reversed; an accidental regression would
     silently let MCP write tools through without any verification.

Gate-review trail: MCP edge-auth design lock; same recipe as the
HTTP edge-auth fitness file.
"""

# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false

from __future__ import annotations

import ast
import inspect
from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


def _tool_files() -> list[Path]:
    """Every BC's `features/*/tool.py` (MCP tool registrar)."""
    out: list[Path] = []
    for path in sorted(tracked_python_files()):
        if not path.is_relative_to(CORA_ROOT):
            continue
        rel = path.relative_to(CORA_ROOT)
        parts = rel.parts
        if len(parts) < 4:
            continue
        if parts[1] != "features":
            continue
        if parts[-1] != "tool.py":
            continue
        out.append(path)
    return out


# ---------- Invariant 1: No SYSTEM_PRINCIPAL_ID in MCP tools ----------


def _ast_has_system_principal_id_in_keyword(tree: ast.AST, kwarg_name: str) -> list[int]:
    """Find every `Call(keyword(arg=kwarg_name, value=Name('SYSTEM_PRINCIPAL_ID')))`.

    Returns the line numbers of every match.
    """
    matches: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg != kwarg_name:
                continue
            if isinstance(kw.value, ast.Name) and kw.value.id == "SYSTEM_PRINCIPAL_ID":
                matches.append(kw.lineno)
    return matches


@pytest.mark.architecture
def test_no_system_principal_id_in_mcp_tool_principal_kwarg() -> None:
    """No MCP `tool.py` may pass `principal_id=SYSTEM_PRINCIPAL_ID`.

    Every site uses `get_mcp_principal_id(ctx)` instead. A new tool
    that copy-paste-defaults to SYSTEM hardcodes the bypass; this
    fitness fails the PR.
    """
    offending: list[str] = []
    for path in _tool_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for line in _ast_has_system_principal_id_in_keyword(tree, "principal_id"):
            offending.append(f"{path.relative_to(CORA_ROOT)}:{line}")
    assert not offending, (
        "MCP tool.py files MUST NOT pass principal_id=SYSTEM_PRINCIPAL_ID "
        ". Replace with "
        f"principal_id=get_mcp_principal_id(ctx). Offending: {offending}"
    )


# ---------- Invariant 2: Every MCP tool takes ctx: Context ----------


def _has_ctx_context_param(tree: ast.AST) -> tuple[bool, list[str]]:
    """Return (every tool fn has a Context-typed param, list of offenders)."""
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        # MCP tool functions are nested inside register(); naming convention is `*_tool`.
        if not node.name.endswith("_tool"):
            continue
        # Look for a parameter whose annotation is `Context[...]` or bare `Context`.
        has_ctx = False
        for arg in node.args.args:
            ann = arg.annotation
            if ann is None:
                continue
            # `Context[Any, Any, Any]` => Subscript(value=Name('Context'), ...).
            if (
                isinstance(ann, ast.Subscript)
                and isinstance(ann.value, ast.Name)
                and ann.value.id == "Context"
            ):
                has_ctx = True
                break
            # Bare `Context` (allowed but unusual).
            if isinstance(ann, ast.Name) and ann.id == "Context":
                has_ctx = True
                break
        if not has_ctx:
            offenders.append(f"{node.name} @ line {node.lineno}")
    return (not offenders, offenders)


@pytest.mark.architecture
def test_every_mcp_tool_function_takes_ctx_context_param() -> None:
    """Every `async def *_tool(...)` inside an MCP `tool.py` MUST declare
    a Context-typed parameter. FastMCP injects Context by type; a tool
    that omits it cannot call `get_mcp_principal_id(ctx)` at all.

    Allows either `Context[Any, Any, Any]` or bare
    `Context`. Catches a new tool that forgets the parameter entirely
    -- the most common MCP edge-auth regression shape.
    """
    offending: list[str] = []
    for path in _tool_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        ok, offenders = _has_ctx_context_param(tree)
        if not ok:
            offending.append(f"{path.relative_to(CORA_ROOT)}: {offenders}")
    assert not offending, (
        "Every MCP tool function (`async def *_tool(...)`) MUST take a "
        "`ctx: Context[Any, Any, Any]` parameter so FastMCP injects the "
        "request-bound Context and `get_mcp_principal_id(ctx)` can resolve "
        f"the verified principal. Offending: {offending}"
    )


# ---------- Invariant 3: get_mcp_principal_id signature pin ----------


@pytest.mark.architecture
def test_get_mcp_principal_id_signature() -> None:
    """`get_mcp_principal_id(ctx: Any) -> UUID` is the public resolver
    contract for every MCP tool. A future refactor that renames a
    kwarg or changes the return type would silently break every tool.
    Pin the signature here.
    """
    from cora.infrastructure.mcp_principal import get_mcp_principal_id

    sig = inspect.signature(get_mcp_principal_id)
    params = list(sig.parameters.values())

    assert len(params) == 1, (
        f"get_mcp_principal_id must take exactly one parameter (ctx); "
        f"got {len(params)}: {[p.name for p in params]}"
    )
    assert params[0].name == "ctx", (
        f"get_mcp_principal_id's parameter must be named 'ctx'; "
        f"got {params[0].name!r}. Tools all call get_mcp_principal_id(ctx) "
        "positionally so a rename here is technically silent at the call "
        "site but renames the convention -- pin it."
    )
    # Return annotation must be UUID (sync-wise; the resolver is plain async-free).
    assert sig.return_annotation in (UUID, "UUID"), (
        f"get_mcp_principal_id must return UUID; got {sig.return_annotation!r}."
    )


# ---------- Invariant 4: BearerAuthMiddleware covers /mcp/* ----------


@pytest.mark.architecture
def test_bearer_middleware_covers_mcp_paths() -> None:
    """The `/mcp/*` skip is removed from `_is_unauthenticated_path`.
    A regression that brings it back would silently let every MCP
    JSON-RPC call through with no bearer verification. Pin the
    inversion.

    Also pins the audience dispatch: MCP paths bind to
    `SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID`, NOT the HTTP Surface
    (AH5: no shared `aud` across Surfaces).
    """
    from cora.infrastructure.auth.bearer_middleware import (
        _is_unauthenticated_path,
        _resolve_expected_audience,
    )
    from cora.infrastructure.routing import (
        SYSTEM_HTTP_SURFACE_ID,
        SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID,
    )

    # Skip-path: /mcp paths are NOT skipped.
    assert _is_unauthenticated_path("/mcp") is False, (
        "/mcp must be bearer-verified. A regression "
        "that re-skips it lets MCP writes through unauthenticated."
    )
    assert _is_unauthenticated_path("/mcp/anything") is False, (
        "/mcp/anything must be bearer-verified."
    )
    assert _is_unauthenticated_path("/mcp/messages/abc") is False, (
        "/mcp/messages/* (SSE messages path) must be bearer-verified."
    )

    # Audience dispatch: MCP routes bind to the MCP Surface.
    assert _resolve_expected_audience("/mcp") == SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID
    assert _resolve_expected_audience("/mcp/anything") == SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID
    # Non-MCP paths bind to the HTTP Surface (AH5: distinct audiences).
    assert _resolve_expected_audience("/actors/123") == SYSTEM_HTTP_SURFACE_ID
    assert _resolve_expected_audience("/") == SYSTEM_HTTP_SURFACE_ID
    assert _resolve_expected_audience("/mcp-fake/admin") == SYSTEM_HTTP_SURFACE_ID, (
        "/mcp-fake/admin shares the /mcp prefix but is NOT the MCP mount; "
        "MUST bind to the HTTP Surface."
    )
