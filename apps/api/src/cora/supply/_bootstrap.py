"""BC-level bootstrap re-exports.

Mirrors the per-BC `_bootstrap` module convention. Today this module
exists solely to preserve the import path
`cora.supply._bootstrap.SYSTEM_PRINCIPAL_ID` used by Supply's MCP
tools. The constant itself lives at
`cora.infrastructure.routing.SYSTEM_PRINCIPAL_ID` (hoisted post-
Phase-3 cleanup so all BCs share one canonical home).

Future Supply-specific BC-level constants (none today) would land
here and join the re-exports below.
"""

from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

__all__ = ["SYSTEM_PRINCIPAL_ID"]
