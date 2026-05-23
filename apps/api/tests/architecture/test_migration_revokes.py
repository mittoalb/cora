"""Every append-only table created in migrations carries a REVOKE
UPDATE / DELETE / TRUNCATE on the cora_app role.

Foundation hardening: the locked decision in
`memory/project_immutability_guarantee.md` says event sourcing's
"events are immutable" must be enforced at the database role level,
not just by application convention. The migration
`20260512230000_init_role_cora_app.sql` establishes the cora_app
role and revokes mutation privileges on the existing events +
entries_* tables; this fitness test makes sure every NEW append-only
table (anything created with `CREATE TABLE events` or
`CREATE TABLE entries_*`) gets the same treatment in some
migration file.

Drift this test catches:

  - A new `entries_run_telemetries` migration without a matching
    REVOKE: cora_app would be granted only SELECT + INSERT today
    (because the role-init migration uses ALTER DEFAULT PRIVILEGES
    with no UPDATE / DELETE), but the explicit REVOKE protects
    against future migrations that might `GRANT ALL` accidentally.
    More importantly, the REVOKE is the documentation: a present
    REVOKE statement signals "this table is intentionally
    append-only" to anyone reading the schema history.
  - A migration that alters an existing entries_* table to allow
    UPDATE without removing the REVOKE (Postgres would not allow
    the UPDATE, but the schema history would lie).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# tests/architecture/test_*.py -> repo root /infra/atlas/migrations
_REPO_ROOT = Path(__file__).resolve().parents[4]
_MIGRATIONS_DIR = _REPO_ROOT / "infra" / "atlas" / "migrations"

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)


def _all_migration_text() -> str:
    """All migration SQL concatenated (single haystack for REVOKE search)."""
    files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    return "\n".join(f.read_text() for f in files)


def _append_only_tables_created() -> set[str]:
    """Names of every append-only table created in any migration.

    Append-only = `events` (the event store) or any table whose name
    starts with `entries_` (the per-category entry tables defined in
    `memory/project_phase_plan.md`'s logbook + entry pattern).
    """
    out: set[str] = set()
    for path in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        for match in _CREATE_TABLE_RE.finditer(path.read_text()):
            name = match.group(1)
            if name == "events" or name.startswith("entries_"):
                out.add(name)
    return out


@pytest.mark.architecture
def test_migrations_directory_exists() -> None:
    """Sanity: the path-resolution heuristic above lands somewhere
    real. Refactors that move the conftest will trip this first."""
    assert _MIGRATIONS_DIR.is_dir(), (
        f"Migrations directory not found at {_MIGRATIONS_DIR}; "
        f"the path-resolution in this test (parents[4]) is wrong."
    )
    assert any(_MIGRATIONS_DIR.glob("*.sql")), (
        f"No .sql files in {_MIGRATIONS_DIR}; either migrations were "
        f"moved or the glob pattern is wrong."
    )


@pytest.mark.architecture
def test_every_append_only_table_has_cora_app_revoke() -> None:
    """REVOKE UPDATE / DELETE / TRUNCATE on cora_app must appear in
    some migration for every events / entries_* table created.

    Pattern accepted: `REVOKE ... ON <table> FROM cora_app`. We do
    not require the exact privilege list (UPDATE / DELETE / TRUNCATE)
    in this test because Postgres will silently no-op REVOKE for
    privileges the role does not hold, and the role-init migration
    already grants only SELECT + INSERT. The presence of any REVOKE
    that names `<table>` and `cora_app` is the documentation signal
    we care about; the integration test in
    `test_cora_app_role_revoke_postgres.py` proves the actual
    behavior."""
    haystack = _all_migration_text()
    tables = _append_only_tables_created()
    assert tables, (
        "No append-only tables found in any migration; either the "
        "schema is empty or the table-name detection is wrong."
    )

    missing: list[str] = []
    for table in sorted(tables):
        # Match: REVOKE <anything> ON [TABLE] <table> FROM <anything> cora_app <anything>
        # The TABLE keyword is optional in Postgres.
        pattern = re.compile(
            rf"REVOKE\b[^;]*\bON\s+(?:TABLE\s+)?{re.escape(table)}\b[^;]*\bcora_app\b",
            re.IGNORECASE | re.DOTALL,
        )
        if not pattern.search(haystack):
            missing.append(table)

    assert not missing, (
        "Append-only tables missing a REVOKE on cora_app:\n"
        + "\n".join(f"  - {t}" for t in missing)
        + "\n\nAdd a `REVOKE UPDATE, DELETE, TRUNCATE ON <table> FROM cora_app;` "
        "statement to the migration that creates the table (see "
        "20260512230000_init_role_cora_app.sql for the canonical shape)."
    )
