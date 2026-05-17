"""MCP write-tool gate for the post-review hardening Phase A.1.

The MCP 2025-11-25 spec defines OAuth 2.1 at the transport layer
but does NOT propagate a verified principal to tool handlers
(the python-sdk's `@server.call_tool()` receives only name +
arguments; verified token / principal is not surfaced via the
session context). Every MCP write-tool in CORA therefore falls
back to `SYSTEM_PRINCIPAL_ID`, which collapses CORA's
operator-in-the-loop audit invariant for any MCP caller.

Until the MCP TokenVerifier integration ships (Phase 8f-d), this
module **fail-closes** every MCP write-tool when the deployment
runs with `require_authenticated_principal=True` (the prod-only
posture enforced by `_enforce_production_principal_policy` in
`api.main`). In that mode the MCP surface still serves read-only
tools (audit + operator dashboards) but every write tool is
deregistered at server-build time, so it never appears in
`tools/list` and cannot be called.

In dev / test (`require_authenticated_principal=False`), all
tools register normally because the SYSTEM-fallback principal is
already the documented dev / test posture for REST as well; MCP
and REST share the same auth posture.

## Read-only classification

A tool is read-only if its name starts with `get_` or `list_` OR
appears in `_EXPLICIT_READS`. The prefix convention covers 34 of
36 read-only tools; the explicit set carries the remaining
exceptions (today: `evaluate_policy`, a Trust BC query that does
not write events).

A future tool that does NOT match either rule is treated as a
write and gated off in prod. To add a new read-only tool, either
name it with a read prefix OR extend `_EXPLICIT_READS`.

## Sources

  - MCP 2025-11-25 Authorization spec:
    https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization.md
  - Python MCP SDK README:
    https://github.com/modelcontextprotocol/python-sdk
  - OWASP Secure Coding Practices (fail-closed for unauth'd writes)
  - NIST SP 800-204 (microservices security; default-deny)

## Lifecycle

Once MCP TokenVerifier integration lands (Phase 8f-d), each
tool's `register(...)` will extract a real principal from the
session context, the SYSTEM-fallback path disappears, and this
module becomes obsolete. Delete it then; do not keep it as
defense-in-depth (that would silently mask future MCP-auth bugs).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cora.infrastructure.logging import get_logger

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from cora.infrastructure.config import Settings

_log = get_logger(__name__)

_READ_ONLY_PREFIXES: tuple[str, ...] = ("get_", "list_")

# Tools that are conceptually reads but do not match the read-only
# prefix convention. Keep this set minimal; prefer renaming new
# tools to use a read prefix over extending this set.
#
#   - evaluate_policy: Trust BC query that returns Allow/Deny;
#     does not write events.
_EXPLICIT_READS: frozenset[str] = frozenset({"evaluate_policy"})


def is_read_only_tool(name: str) -> bool:
    """True iff the MCP tool with this name is a read-only query."""
    return name in _EXPLICIT_READS or name.startswith(_READ_ONLY_PREFIXES)


def gate_mcp_write_tools(mcp: FastMCP, settings: Settings) -> None:
    """Deregister every MCP write-tool when MCP-auth is not yet wired.

    The gate fires when `require_authenticated_principal` is True
    (the prod-only posture). In that mode every non-read-only tool
    is removed from the FastMCP server's tool manager so it never
    appears in `tools/list` and cannot be invoked.

    Uses `mcp._tool_manager.list_tools()` (sync) rather than
    `await mcp.list_tools()` (async) so the gate can run inside
    `create_app()`'s sync construction path. ToolManager is the
    public MCP SDK class behind FastMCP's facade; the private-
    attribute access is acceptable here because this whole module
    is a hardening shim slated for deletion at Phase 8f-d.

    Idempotent and safe to call once after all `register_*_tools`
    calls have completed; no-op when `require_authenticated_principal`
    is False (dev / test).
    """
    if not settings.require_authenticated_principal:
        return

    tools = mcp._tool_manager.list_tools()  # pyright: ignore[reportPrivateUsage]
    removed: list[str] = []
    for tool in tools:
        if not is_read_only_tool(tool.name):
            mcp.remove_tool(tool.name)
            removed.append(tool.name)

    if removed:
        _log.warning(
            "mcp.write_tools_gated",
            reason=(
                "require_authenticated_principal=True but MCP TokenVerifier "
                "integration not yet wired; write-tools fail-closed until "
                "Phase 8f-d. Use REST endpoints for write operations."
            ),
            count=len(removed),
            tools=sorted(removed),
        )


__all__ = ["gate_mcp_write_tools", "is_read_only_tool"]
