"""Integration tests for `verify_bootstrap_seed_present`.

Covers the three branches added in Phase B Iter C-1:
  1. trust_policy_id == V2 → load V2 policy + all 3 Surfaces; assert
     V2 binds to HTTP Surface (GR3 BC-7 binding check).
  2. trust_policy_id == V1 → load V1 policy + log deprecation WARN.
  3. Otherwise → no-op.

Also pins the failure paths: missing V2 stream / missing seeded
Surface / V2 mis-bound to non-HTTP surface / missing V1 stream.

Closes GR3 BC-6 (verifier had zero tests pre-this).
"""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch

import asyncpg
import pytest

from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.trust._bootstrap import (
    SYSTEM_BOOTSTRAP_POLICY_ID,
    SYSTEM_BOOTSTRAP_POLICY_V2_ID,
    verify_bootstrap_seed_present,
)
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)


def _deps_with_trust_policy_id(db_pool: asyncpg.Pool, policy_id: object) -> Kernel:
    """Build a Kernel with a custom `trust_policy_id` setting.

    Uses `dataclasses.replace` on the Settings dataclass — avoids
    directly constructing a fresh Kernel, which would trip the
    architecture-fitness single-construction-site invariant.
    """
    base = build_postgres_deps(db_pool, now=_NOW)
    new_settings = Settings.model_validate(
        {**base.settings.model_dump(), "trust_policy_id": policy_id},
    )
    return replace(base, settings=new_settings)


@pytest.mark.integration
async def test_verify_passes_when_v2_policy_and_surfaces_all_seeded(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: V2 + 3 Surfaces present (the test DB template has
    them via the Phase B seed migration)."""
    deps = _deps_with_trust_policy_id(db_pool, SYSTEM_BOOTSTRAP_POLICY_V2_ID)
    await verify_bootstrap_seed_present(deps)  # no exception


@pytest.mark.integration
async def test_verify_passes_when_v1_policy_seeded(
    db_pool: asyncpg.Pool,
) -> None:
    """V1 path: V1 stream exists → verifier completes without exception.

    A deprecation WARN is emitted via structlog (visible to operators
    in production logs); we don't pin it here because structlog +
    caplog + xdist capture interactions are fragile. The WARN's
    presence is exercised manually + via the structlog event-name
    constant; the load-bearing behavior is 'no boot failure on V1'.
    """
    deps = _deps_with_trust_policy_id(db_pool, SYSTEM_BOOTSTRAP_POLICY_ID)
    await verify_bootstrap_seed_present(deps)  # no exception


@pytest.mark.integration
async def test_verify_noop_when_custom_policy_id_configured(
    db_pool: asyncpg.Pool,
) -> None:
    """A custom (non-seeded) policy id falls into the no-op branch.
    Operators using their own admin Policy aren't blocked at boot."""
    from uuid import UUID

    custom = UUID("01900000-0000-7000-8000-0000000ccccc")
    deps = _deps_with_trust_policy_id(db_pool, custom)
    await verify_bootstrap_seed_present(deps)  # no exception


@pytest.mark.integration
async def test_verify_noop_when_no_policy_id_configured(
    db_pool: asyncpg.Pool,
) -> None:
    """trust_policy_id=None means AllowAllAuthorize is wired; verifier
    has nothing to check."""
    deps = _deps_with_trust_policy_id(db_pool, None)
    await verify_bootstrap_seed_present(deps)  # no exception


@pytest.mark.integration
async def test_verify_raises_when_v2_policy_stream_missing(
    db_pool: asyncpg.Pool,
) -> None:
    """V2 configured but the policy stream isn't seeded — fail-fast
    with a runbook pointer."""
    deps = _deps_with_trust_policy_id(db_pool, SYSTEM_BOOTSTRAP_POLICY_V2_ID)
    with (
        patch("cora.trust._bootstrap.load_policy", return_value=None),
        pytest.raises(RuntimeError, match="V2 bootstrap policy"),
    ):
        await verify_bootstrap_seed_present(deps)


@pytest.mark.integration
async def test_verify_raises_when_seeded_surface_missing(
    db_pool: asyncpg.Pool,
) -> None:
    """V2 configured + V2 stream present but one of the 3 Surfaces is
    missing — AH14 partial-fail mitigation."""
    deps = _deps_with_trust_policy_id(db_pool, SYSTEM_BOOTSTRAP_POLICY_V2_ID)
    with (
        patch("cora.trust._bootstrap.load_surface", return_value=None),
        pytest.raises(RuntimeError, match=r"seeded Surface .* is missing"),
    ):
        await verify_bootstrap_seed_present(deps)


@pytest.mark.integration
async def test_verify_raises_when_v2_policy_misbound_to_non_http_surface(
    db_pool: asyncpg.Pool,
) -> None:
    """GR3 BC-7: V2 policy loaded but folded `surface_id !=
    SYSTEM_HTTP_SURFACE_ID` (e.g., post-seed mutation, or unauthorized
    PolicyDefined appended to V2 stream). The verifier catches it
    instead of silently denying every request post-Iter-C-2."""
    from cora.trust.aggregates.policy import PolicyName
    from cora.trust.aggregates.policy.state import Policy

    deps = _deps_with_trust_policy_id(db_pool, SYSTEM_BOOTSTRAP_POLICY_V2_ID)
    # Stub V2 policy to fold with a non-HTTP surface_id (corrupted).
    from uuid import UUID

    bogus_policy = Policy(
        id=SYSTEM_BOOTSTRAP_POLICY_V2_ID,
        name=PolicyName("Tampered"),
        conduit_id=UUID(int=0),
        permitted_principals=frozenset(),
        permitted_commands=frozenset(),
        surface_id=UUID(int=99),  # NOT SYSTEM_HTTP_SURFACE_ID
    )
    with (
        patch("cora.trust._bootstrap.load_policy", return_value=bogus_policy),
        pytest.raises(RuntimeError, match="folded with surface_id="),
    ):
        await verify_bootstrap_seed_present(deps)


@pytest.mark.integration
async def test_verify_raises_when_v1_policy_stream_missing(
    db_pool: asyncpg.Pool,
) -> None:
    """V1 configured but the V1 stream is somehow missing (corrupted
    DB / unrestored backup). Fail-fast with a runbook pointer."""
    deps = _deps_with_trust_policy_id(db_pool, SYSTEM_BOOTSTRAP_POLICY_ID)
    with (
        patch("cora.trust._bootstrap.load_policy", return_value=None),
        pytest.raises(RuntimeError, match="legacy V1 bootstrap policy"),
    ):
        await verify_bootstrap_seed_present(deps)
