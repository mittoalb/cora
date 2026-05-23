"""Trust BC re-exports, system-policy / system-surface UUIDs, and the
boot-time seed-verification helper.

See `cora/trust/authorize.py` for the bootstrap workflow,
`memory/project_bootstrap_policy_design.md` for the bootstrap rationale,
and `memory/project_conduit_injection_design.md` for the Surface
decomposition and the V1→V2 bootstrap-policy transition.
"""

from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.routing import (
    SYSTEM_HTTP_SURFACE_ID,
    SYSTEM_MCP_STDIO_SURFACE_ID,
    SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID,
    SYSTEM_PRINCIPAL_ID,
)
from cora.trust.aggregates.policy import load_policy
from cora.trust.aggregates.surface import load_surface

_log = get_logger(__name__)

# V1 Bootstrap Policy id. Bound to (conduit=nil, surface=nil).
# Operationally inert: handler call sites pass real surface_id
# starting with the V2 bootstrap; V1's nil-surface no longer matches.
# Kept as the named export for backward compat with existing tests +
# any deployments not yet migrated.
SYSTEM_BOOTSTRAP_POLICY_ID = UUID("00000000-0000-0000-0000-000000000001")

# V2 Bootstrap Policy id. Bound to (conduit=nil, surface=HTTP).
# Production deployments set
# `TRUST_POLICY_ID=00000000-0000-0000-0000-000000000002` to point at
# this; the verifier below catches operators still on V1 and logs a
# deprecation WARN.
SYSTEM_BOOTSTRAP_POLICY_V2_ID = UUID("00000000-0000-0000-0000-000000000002")

# Default Surfaces seeded by
# `20260519200000_seed_default_surfaces_and_v2_policy.sql`.
#
# Re-exported above from `cora.infrastructure.routing` so historical
# `from cora.trust._bootstrap import SYSTEM_HTTP_SURFACE_ID` callers
# keep working. Canonical home is infrastructure so every BC's
# route/tool can import the per-request resolvers without violating
# tach BC-isolation.


async def verify_bootstrap_seed_present(deps: Kernel) -> None:
    """Fail-fast at lifespan start when the configured bootstrap seed
    stream — or its dependencies — is missing.

    Three modes:

    1. `trust_policy_id == SYSTEM_BOOTSTRAP_POLICY_V2_ID`: verify the
       V2 policy stream + the 3 seeded Surface streams exist. V2
       references HTTP Surface; without Surface streams, evaluate
       would Allow on a phantom surface_id and the traversal audit
       log silently skips entries. Partial-fail mitigation.

    2. `trust_policy_id == SYSTEM_BOOTSTRAP_POLICY_ID` (V1): verify
       the V1 stream exists AND log a deprecation WARN. V1 is
       operationally inert today (binds to nil-surface; new handler
       call sites pass real surface_id). Operators should migrate to
       V2 via `TRUST_POLICY_ID=…0002`. R2B R-1 mitigation.

    3. Otherwise no-op (custom operator policies are the operator's
       responsibility to verify).
    """
    settings = deps.settings

    if settings.trust_policy_id == SYSTEM_BOOTSTRAP_POLICY_V2_ID:
        policy = await load_policy(deps.event_store, SYSTEM_BOOTSTRAP_POLICY_V2_ID)
        if policy is None:
            msg = (
                f"Configured trust_policy_id={SYSTEM_BOOTSTRAP_POLICY_V2_ID} "
                "(V2 bootstrap policy) but the seed stream is missing "
                "from the event store. Re-run `make migrate-apply` — "
                "the seed migration "
                "20260519200000_seed_default_surfaces_and_v2_policy.sql "
                "is idempotent (ON CONFLICT DO NOTHING) and safe to "
                "re-apply. See memory/project_conduit_injection_design.md."
            )
            raise RuntimeError(msg)

        # V2 binds to SYSTEM_HTTP_SURFACE_ID; without all 3 seeded
        # Surfaces present, the audit / authz substrate is broken
        # (partial-fail).
        for surface_id in (
            SYSTEM_HTTP_SURFACE_ID,
            SYSTEM_MCP_STDIO_SURFACE_ID,
            SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID,
        ):
            surface = await load_surface(deps.event_store, surface_id)
            if surface is None:
                msg = (
                    f"trust_policy_id={SYSTEM_BOOTSTRAP_POLICY_V2_ID} (V2) "
                    f"is configured but seeded Surface {surface_id} is "
                    "missing from the event store — V2 references the "
                    "HTTP Surface and the audit path expects all 3. "
                    "Re-run `make migrate-apply`; the seed migration is "
                    "idempotent."
                )
                raise RuntimeError(msg)

        # GR3 BC-7: also assert V2 policy's surface_id binding is correct.
        # A typo'd / mis-wired V2 (folded surface_id != HTTP) would silently
        # deny every request post-Iter-C-2.
        if policy.surface_id != SYSTEM_HTTP_SURFACE_ID:
            msg = (
                f"trust_policy_id={SYSTEM_BOOTSTRAP_POLICY_V2_ID} (V2) "
                f"was loaded but folded with surface_id={policy.surface_id} "
                f"instead of the expected SYSTEM_HTTP_SURFACE_ID "
                f"({SYSTEM_HTTP_SURFACE_ID}). The seed migration may have "
                "been mutated post-seed, or a non-seed PolicyDefined event "
                "was appended to this stream. Investigate the event log."
            )
            raise RuntimeError(msg)
        return

    if settings.trust_policy_id == SYSTEM_BOOTSTRAP_POLICY_ID:
        policy = await load_policy(deps.event_store, SYSTEM_BOOTSTRAP_POLICY_ID)
        if policy is None:
            msg = (
                f"Configured trust_policy_id={SYSTEM_BOOTSTRAP_POLICY_ID} "
                "(legacy V1 bootstrap policy) but the seed stream is "
                "missing from the event store. Either re-run "
                "`make migrate-apply` (the seed migration is idempotent) "
                "OR migrate to V2 by setting "
                f"TRUST_POLICY_ID={SYSTEM_BOOTSTRAP_POLICY_V2_ID}. "
                "See memory/project_conduit_injection_design.md WI9."
            )
            raise RuntimeError(msg)
        _log.warning(
            "trust.v1_bootstrap_policy_deprecation",
            policy_id=str(SYSTEM_BOOTSTRAP_POLICY_ID),
            recommended_replacement=str(SYSTEM_BOOTSTRAP_POLICY_V2_ID),
            runbook="docs/stack/deployment.md",
            reason=(
                "V1 bootstrap policy is operationally inert (binds "
                "to nil-surface; new handler call sites pass real "
                "surface_id). Set TRUST_POLICY_ID to the V2 id."
            ),
        )


__all__ = [
    "SYSTEM_BOOTSTRAP_POLICY_ID",
    "SYSTEM_BOOTSTRAP_POLICY_V2_ID",
    "SYSTEM_HTTP_SURFACE_ID",
    "SYSTEM_MCP_STDIO_SURFACE_ID",
    "SYSTEM_MCP_STREAMABLE_HTTP_SURFACE_ID",
    "SYSTEM_PRINCIPAL_ID",
    "verify_bootstrap_seed_present",
]
