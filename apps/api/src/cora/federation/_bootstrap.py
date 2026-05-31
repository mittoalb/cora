"""Federation BC bootstrap reservation.

Reserved for federation-specific startup work (for example,
seeding the per-facility Seal singleton at deployment time). The
hook is a no-op today; slices that need bootstrap wiring fill it
in when they land.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel


async def bootstrap_federation(kernel: Kernel) -> None:
    """Reserved for federation-specific startup. No-op today."""
    _ = kernel


__all__ = ["bootstrap_federation"]
