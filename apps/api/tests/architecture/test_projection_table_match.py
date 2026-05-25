"""Every projection registered via `register_<bc>_projections` has a
matching `CREATE TABLE proj_<name>` migration.

Phase-8e D11.2. Without this check, a developer can register a
projection in code, the worker tries to advance it, and the bookmark
read fails (no row in projection_bookmarks because the projection's
migration never landed). This test catches that misalignment at PR
time.

Discovery uses the same lifespan-equivalent registration the FastAPI
app does: import every BC's `register_<bc>_projections` function
(when present), call it against an empty registry, then assert each
registered projection's name appears as a `CREATE TABLE` in some
migration.

When 8e-1a ships, no BC has projection registration yet so the test
skips. 8e-1b (Access projection) and beyond exercise it.
"""

from __future__ import annotations

import importlib
import re
from typing import TYPE_CHECKING

import pytest

from cora.infrastructure.projection import ProjectionRegistry
from tests.architecture.conftest import BCS, tracked_migration_files

if TYPE_CHECKING:
    from cora.infrastructure.kernel import Kernel

_CREATE_PROJ_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(proj_[a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)
_RENAME_PROJ_TABLE_RE = re.compile(
    r"ALTER\s+TABLE\s+(proj_[a-zA-Z_][a-zA-Z0-9_]*)\s+RENAME\s+TO\s+(proj_[a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)
_DROP_PROJ_TABLE_RE = re.compile(
    r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(proj_[a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)


def _proj_tables_created() -> set[str]:
    """Return the set of `proj_*` tables that currently exist after applying
    all migrations in order, following any `ALTER TABLE ... RENAME TO ...`
    or `DROP TABLE` along the way. Without this, a forward-only rename
    would leave the old name in the set forever and the new name absent
    (orphan + missing-table double false positive)."""
    out: set[str] = set()
    for path in tracked_migration_files():
        text = path.read_text()
        for match in _CREATE_PROJ_TABLE_RE.finditer(text):
            out.add(match.group(1))
        for match in _RENAME_PROJ_TABLE_RE.finditer(text):
            old_name, new_name = match.group(1), match.group(2)
            out.discard(old_name)
            out.add(new_name)
        for match in _DROP_PROJ_TABLE_RE.finditer(text):
            out.discard(match.group(1))
    return out


def _populate_registry_from_bcs() -> ProjectionRegistry:
    """Import every BC, look for `register_<bc>_projections`, call it
    with the empty registry. BCs without projections are silently
    skipped (no exported function = no projections to register)."""
    registry = ProjectionRegistry()
    # We pass `None` for `deps` because the registration functions
    # we'll write only need it if the projection construction does;
    # current 8e-1b ActorSummaryProjection doesn't (the projection is
    # stateless beyond its name + subscribed_event_types).
    deps_stub: Kernel | None = None
    for bc in BCS:
        try:
            module = importlib.import_module(f"cora.{bc}")
        except ModuleNotFoundError:
            continue
        register = getattr(module, f"register_{bc}_projections", None)
        if register is None:
            continue
        register(registry, deps_stub)
    return registry


@pytest.mark.architecture
def test_every_registered_projection_has_a_create_table_migration() -> None:
    """A projection name in the registry must appear in some migration's
    `CREATE TABLE proj_<name>` statement. Catches code-level
    registration without the underlying schema."""
    registry = _populate_registry_from_bcs()
    if registry.is_empty():
        pytest.skip(
            "No projections registered yet (8e-1a ships the framework only; "
            "8e-1b adds the first BC-side registration)."
        )

    tables_in_migrations = _proj_tables_created()
    missing: list[str] = sorted(
        name for name in registry.names() if name not in tables_in_migrations
    )
    assert not missing, (
        "Projections registered but missing CREATE TABLE migration:\n"
        + "\n".join(f"  - {n}" for n in missing)
        + "\n\nEvery projection must have a corresponding migration creating "
        "its `proj_<name>` table + an INSERT into projection_bookmarks for "
        "first-run sentinel registration."
    )


@pytest.mark.architecture
def test_every_proj_table_in_migrations_has_a_registration() -> None:
    """Inverse direction: a `CREATE TABLE proj_<name>` migration with
    no matching code registration is an orphan (table but no consumer
    keeping it up-to-date). Catches deletion of a projection without
    cleaning up its migration."""
    registry = _populate_registry_from_bcs()
    tables_in_migrations = _proj_tables_created()
    if not tables_in_migrations:
        pytest.skip("No proj_* tables exist yet.")

    registered = registry.names()
    orphans: list[str] = sorted(t for t in tables_in_migrations if t not in registered)
    assert not orphans, (
        "proj_* tables exist in migrations but no code registration:\n"
        + "\n".join(f"  - {t}" for t in orphans)
        + "\n\nEither register the projection in a `register_<bc>_projections` "
        "function or remove the orphan table via a forward migration."
    )
