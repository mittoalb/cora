"""SEC-FED-02: every Federation BC projection migration ships with
Row-Level Security FORCED on the cora_app role plus at least two
`CREATE POLICY` statements (one read, one write). The pattern matches
`actor_profile` (per `memory/project_pii_vault_implementation_design`):
ENABLE row level security, FORCE row level security so the owner
role cannot bypass, and two flat policies for cora_app. Without
FORCE, a maintenance task running under the owner role implicitly
reads everything; without the two policies, defence-in-depth on
peer-facility material is missing.

The drift this catches is mechanical: a new
`*proj_federation_*.sql` migration shipped without the RLS-FORCE
preamble (because it was copied from a pre-RLS template or the
section was lost during a rebase). The fitness test enumerates
migrations via `tracked_migration_files()` so half-staged migrations
during a pre-commit run cannot leak into the check (same rationale
as `test_migration_revokes.py`).

The pattern is structural, not behavioural: integration tests prove
RLS actually denies cross-facility reads. This test only asserts
that the RLS preamble survives every future federation projection
migration.
"""

from __future__ import annotations

import re

import pytest

from tests.architecture.conftest import tracked_migration_files

_FEDERATION_PROJECTION_RE = re.compile(r"proj_federation_")

_ENABLE_RLS_RE = re.compile(r"ENABLE\s+ROW\s+LEVEL\s+SECURITY", re.IGNORECASE)
_FORCE_RLS_RE = re.compile(r"FORCE\s+ROW\s+LEVEL\s+SECURITY", re.IGNORECASE)
_CREATE_POLICY_RE = re.compile(r"\bCREATE\s+POLICY\b", re.IGNORECASE)

_MIN_POLICIES = 2


def _federation_projection_migrations() -> list[tuple[str, str]]:
    """`(filename, sql_text)` pairs for every tracked migration whose
    filename references a `proj_federation_*` projection table.

    Filename match (not SQL grep) so that migrations which only
    ALTER or DROP a projection table are not pulled in; those land
    in their own slice with their own ownership of RLS posture.
    """
    out: list[tuple[str, str]] = []
    for path in tracked_migration_files():
        if _FEDERATION_PROJECTION_RE.search(path.name):
            out.append((path.name, path.read_text()))
    return out


@pytest.mark.architecture
def test_federation_projection_migrations_enumerated() -> None:
    """Sanity: at least one `proj_federation_*` migration is tracked.

    Refactors that move the migrations directory or rename the
    federation projections (e.g. dropping the `proj_federation_`
    prefix) will trip this first, before the RLS-FORCE check falsely
    reports "all zero migrations comply".
    """
    migrations = _federation_projection_migrations()
    assert migrations, (
        "No `proj_federation_*` migrations found under "
        "infra/atlas/migrations/. Either the projection table prefix "
        "changed or `tracked_migration_files()` lost them."
    )


@pytest.mark.architecture
@pytest.mark.parametrize(
    "filename,sql",
    _federation_projection_migrations(),
    ids=lambda v: v if isinstance(v, str) and v.endswith(".sql") else "sql",
)
def test_federation_projection_migration_enforces_rls_force(
    filename: str,
    sql: str,
) -> None:
    """The migration ENABLEs + FORCEs RLS and creates at least two policies."""
    problems: list[str] = []
    if not _ENABLE_RLS_RE.search(sql):
        problems.append("missing `ENABLE ROW LEVEL SECURITY`")
    if not _FORCE_RLS_RE.search(sql):
        problems.append("missing `FORCE ROW LEVEL SECURITY`")
    policies = len(_CREATE_POLICY_RE.findall(sql))
    if policies < _MIN_POLICIES:
        problems.append(
            f"only {policies} `CREATE POLICY` statement(s); expected >= {_MIN_POLICIES} "
            "(one read, one write per the actor_profile precedent)"
        )

    assert not problems, (
        f"{filename} is missing the RLS-FORCE preamble:\n  "
        + "\n  ".join(problems)
        + "\n\nSEC-FED-02: federation projection tables hold cross-facility "
        "material (seal heads, credential refs, permit terms). The owner-role "
        "bypass that ENABLE alone permits is unacceptable here; FORCE plus "
        "two flat cora_app policies (read + write) is the locked posture. See "
        "20260530210200_init_proj_federation_seal_summary.sql for the canonical shape."
    )
