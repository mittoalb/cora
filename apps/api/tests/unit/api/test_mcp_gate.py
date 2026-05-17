"""Pure-classifier tests for `cora.api.mcp_gate.is_read_only_tool`.

The gate's effect on a real FastMCP server is exercised separately
in the contract tier; this module pins only the read-only
classifier so future contributors adding a new tool can reason
about which side of the gate it falls on without booting the app.
"""

import pytest

from cora.api.mcp_gate import is_read_only_tool


@pytest.mark.unit
@pytest.mark.parametrize(
    "name",
    [
        "get_agent",
        "get_run",
        "get_dataset",
        "list_actors",
        "list_runs",
        "list_decisions",
        "evaluate_policy",  # explicit-read exception
    ],
)
def test_read_only_tools_classified_as_reads(name: str) -> None:
    assert is_read_only_tool(name) is True


@pytest.mark.unit
@pytest.mark.parametrize(
    "name",
    [
        "register_actor",
        "define_agent",
        "start_run",
        "promote_caution_proposal",
        "re_debrief_run",
        "rate_decision",
        "amend_clearance",
        "mark_supply_unavailable",
        "update_asset_settings",
        "remove_plan_wire",
    ],
)
def test_write_tools_classified_as_writes(name: str) -> None:
    assert is_read_only_tool(name) is False


@pytest.mark.unit
def test_unknown_tool_defaults_to_write() -> None:
    """Fail-closed: an unrecognized tool name is treated as a write
    so a freshly added tool doesn't accidentally bypass the gate."""
    assert is_read_only_tool("unknown_future_tool") is False
