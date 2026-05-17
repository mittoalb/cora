"""BC-level bootstrap re-exports for the Agent BC.

Mirrors the per-BC `_bootstrap` module convention. Today this module
exists solely to preserve the import path
`cora.agent._bootstrap.SYSTEM_PRINCIPAL_ID` used by Agent's MCP
tools. The constant itself lives at
`cora.infrastructure.routing.SYSTEM_PRINCIPAL_ID` (hoisted post-
Phase-3 cleanup so all BCs share one canonical home).
"""

from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

__all__ = ["SYSTEM_PRINCIPAL_ID"]
