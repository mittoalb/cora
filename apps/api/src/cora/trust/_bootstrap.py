"""Trust BC re-exports, the System Bootstrap Policy id, and the
boot-time seed-verification helper.

See `cora/trust/authorize.py` for the bootstrap workflow and
`memory/project_bootstrap_policy_design.md` for design rationale.
"""

from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID
from cora.trust.aggregates.policy import load_policy

SYSTEM_BOOTSTRAP_POLICY_ID = UUID("00000000-0000-0000-0000-000000000001")


async def verify_bootstrap_seed_present(deps: Kernel) -> None:
    """Fail-fast at lifespan start when the seed stream is missing
    under a bootstrap-pointed deployment. Without this, a corrupted
    DB silently 403s every request. No-op when `trust_policy_id` is
    not the bootstrap UUID.
    """
    if deps.settings.trust_policy_id != SYSTEM_BOOTSTRAP_POLICY_ID:
        return
    policy = await load_policy(deps.event_store, SYSTEM_BOOTSTRAP_POLICY_ID)
    if policy is None:
        msg = (
            f"Configured trust_policy_id={SYSTEM_BOOTSTRAP_POLICY_ID} "
            "(SYSTEM_BOOTSTRAP_POLICY_ID) but the seed stream is missing "
            "from the event store. Re-run `make migrate-apply` against "
            "the deployment's database — the seed migration "
            "20260519000000_seed_bootstrap_policy.sql is idempotent and "
            "safe to re-apply (ON CONFLICT DO NOTHING). See "
            "memory/project_bootstrap_policy_design.md (WI3)."
        )
        raise RuntimeError(msg)


__all__ = [
    "SYSTEM_BOOTSTRAP_POLICY_ID",
    "SYSTEM_PRINCIPAL_ID",
    "verify_bootstrap_seed_present",
]
