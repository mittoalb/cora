"""BC-level bootstrap re-exports.

Today this module exists solely to preserve the import path
`cora.subject._bootstrap.SYSTEM_PRINCIPAL_ID` used by Subject's MCP
tools. The constant itself lives at
`cora.infrastructure.routing.SYSTEM_PRINCIPAL_ID` (one canonical
fallback, post-Phase-3 cleanup).

Future Subject-specific BC-level constants (none today) would land
here and join the re-exports below.
"""

from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

__all__ = ["SYSTEM_PRINCIPAL_ID"]
