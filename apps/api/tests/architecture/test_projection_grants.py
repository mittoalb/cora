"""Every `CREATE TABLE proj_*` migration carries a matching GRANT
on cora_app.

Mirror of `test_migration_revokes.py`, but
for the read-side projection tables: proj_* tables are mutable
(rebuildable from events) so cora_app needs SELECT/INSERT/UPDATE/
DELETE on them. Without the explicit GRANT, the projection worker
running as cora_app would silently fail to write.

Pre-cora_app role split, these grants were inherited from the role
owner; now they must be explicit per migration. Catches a future
projection migration that creates `proj_x` but forgets the GRANT.
"""

from __future__ import annotations

import re

import pytest

from tests.architecture.conftest import tracked_migration_files

_CREATE_PROJ_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(proj_[a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)


def _all_migration_text() -> str:
    return "\n".join(f.read_text() for f in tracked_migration_files())


def _proj_tables_created() -> set[str]:
    out: set[str] = set()
    for path in tracked_migration_files():
        for match in _CREATE_PROJ_TABLE_RE.finditer(path.read_text()):
            out.add(match.group(1))
    return out


@pytest.mark.architecture
def test_every_proj_table_has_cora_app_grant() -> None:
    """Pattern accepted: `GRANT ... ON [TABLE] <table> ... TO cora_app`.
    Doesn't enforce the exact privilege list because Postgres GRANT
    allows additive specification; the presence of any GRANT to
    cora_app naming the table is the documentation signal."""
    haystack = _all_migration_text()
    tables = _proj_tables_created()
    if not tables:
        pytest.skip(
            "No proj_* tables created yet (the framework ships first; "
            "the first projection table lands in a follow-up)."
        )

    missing: list[str] = []
    for table in sorted(tables):
        pattern = re.compile(
            rf"GRANT\b[^;]*\bON\s+(?:TABLE\s+)?{re.escape(table)}\b[^;]*\bTO\s+[^;]*cora_app\b",
            re.IGNORECASE | re.DOTALL,
        )
        if not pattern.search(haystack):
            missing.append(table)

    assert not missing, (
        "proj_* tables missing a GRANT on cora_app:\n"
        + "\n".join(f"  - {t}" for t in missing)
        + "\n\nAdd a `GRANT SELECT, INSERT, UPDATE, DELETE ON <table> TO cora_app;` "
        "statement to the migration that creates the table. Projection tables "
        "are read-side mutable (rebuildable from events) so they get full DML, "
        "unlike events / entries_* which are append-only."
    )
