"""MCP tool registration for the Agent BC.

`register_agent_tools(mcp, *, get_handlers)` registers each slice's
MCP tool on the shared FastMCP server. `get_handlers` is a callable
returning the `AgentHandlers` bundle wired during the FastAPI
lifespan; it's invoked per tool call so the latest wiring is
always used.
"""

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from cora.agent.features.define_agent import tool as define_agent_tool
from cora.agent.features.deprecate_agent import tool as deprecate_agent_tool
from cora.agent.features.get_agent import tool as get_agent_tool
from cora.agent.features.re_debrief_run import tool as re_debrief_run_tool
from cora.agent.features.re_debrief_run.handler import IdempotentHandler as ReDebriefRunHandler
from cora.agent.features.version_agent import tool as version_agent_tool
from cora.agent.wire import AgentHandlers


def register_agent_tools(
    mcp: FastMCP,
    *,
    get_handlers: Callable[[], AgentHandlers],
) -> None:
    """Register every Agent slice's MCP tool on the FastMCP server."""
    define_agent_tool.register(
        mcp,
        get_handler=lambda: get_handlers().define_agent,
    )
    version_agent_tool.register(
        mcp,
        get_handler=lambda: get_handlers().version_agent,
    )
    deprecate_agent_tool.register(
        mcp,
        get_handler=lambda: get_handlers().deprecate_agent,
    )
    get_agent_tool.register(
        mcp,
        get_handler=lambda: get_handlers().get_agent,
    )
    # 8f-c iter 1: re_debrief_run handler is Optional in the bundle
    # (None when kernel.llm is unwired). The tool's lambda dereferences
    # at call time and raises a RuntimeError to surface as MCP isError;
    # this matches the REST 503 semantics. Production deploys with
    # ANTHROPIC_API_KEY set never hit the None branch.
    re_debrief_run_tool.register(
        mcp,
        get_handler=lambda: _resolve_re_debrief_run(get_handlers()),
    )


def _resolve_re_debrief_run(handlers: AgentHandlers) -> ReDebriefRunHandler:
    """Dereference the Optional re_debrief_run handler with a loud
    failure when unwired. Mirrors the REST route's 503 path."""
    if handlers.re_debrief_run is None:
        msg = (
            "re_debrief_run is unavailable: kernel.llm is not wired "
            "(ANTHROPIC_API_KEY not configured)."
        )
        raise RuntimeError(msg)
    return handlers.re_debrief_run
