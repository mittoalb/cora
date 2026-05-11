"""BC-level bootstrap re-exports for the Run BC.

Mirrors `cora.recipe._bootstrap` / `cora.equipment._bootstrap`. Today
this module exists solely to preserve the import path
`cora.run._bootstrap.SYSTEM_PRINCIPAL_ID` used by Run's MCP tools.
The constant itself lives at `cora.infrastructure.routing.SYSTEM_PRINCIPAL_ID`.

Future Run-specific BC-level constants (none today) would land here.
"""

from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID

__all__ = ["SYSTEM_PRINCIPAL_ID"]
