"""Integration-test fixtures: per-test Postgres database + shared softIOC.

Adds:

- `db_pool` (function-scoped): per-test database cloned via
  `CREATE DATABASE ... TEMPLATE migrated_db` (file-copy fast, full
  isolation, no TRUNCATE bookkeeping).
- `_pin_epics_env` (session-scoped, autouse): locks `EPICS_CA_*` env
  vars to a loopback port for the whole worker. MUST run before any
  aioca / p4p import (the C library reads env at first use AND
  caches per-process).
- `softioc` (module-scoped): spawns an `epicscorelibs.ioc` subprocess
  serving the test PV menu. Tests for `CaprotoControlPort` AND
  `EpicsCaControlPort` (and future `EpicsPvaControlPort`) reuse it.
- `_purge_aioca_caches` (function-scoped, autouse): calls
  `aioca.purge_channel_caches()` after each test so subscriptions
  don't leak across tests within the same module.

Per [[project_control_port_test_isolation_research]], this is the
corpus-unanimous pattern across Diamond aioca + ophyd-async + fastcs
+ caproto's own client tests. The session-scoped env pin + module-
scoped subprocess + function-scoped purge combination dodges the
process-global `libca` / `pvxs` broadcaster state problem without
calling the unsafe `ca_context_destroy`.

The session-scoped postgres fixtures live in `tests/conftest.py`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingTypeStubs=false, reportUnusedFunction=false

import asyncio
import contextlib
import os
from collections.abc import AsyncGenerator, Generator, Iterator
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

from cora.infrastructure.postgres.pool import create_pool
from tests._postgres import normalize_async_url
from tests.integration._softioc import (
    emit_db_file,
    free_localhost_port,
    start_softioc,
    stop_softioc_cleanly,
    wait_for_softioc_ready,
)


@pytest.fixture(scope="session", autouse=True)
def _pin_epics_env() -> Iterator[None]:
    """Lock EPICS env vars to a loopback port for the whole xdist worker.

    Runs before any test (autouse + session scope). Per the corpus
    pattern, aioca / p4p read these vars at first use AND keep the
    C-level broadcaster bound for the lifetime of the process. Setting
    them once at session start (via `os.environ`, not `monkeypatch`)
    keeps the parent's CA / PVA client pointed at the right loopback
    port for every test in this worker.

    Per-worker port uniqueness is preserved: xdist runs each worker
    as a separate OS process, each gets its own `_pin_epics_env`
    invocation, each picks its own ephemeral port. The `softioc`
    fixture binds an IOC to that port.

    Originally set via `monkeypatch` per-test (Stage-1b pattern); that
    works for caproto's per-`Context()` client (no shared state) but
    breaks for aioca (process-global state). Session-scope is the only
    pattern that satisfies both clients without subprocess-per-test
    overhead. See [[project_control_port_test_isolation_research]] for
    the full corpus + rationale.
    """
    ca_port = free_localhost_port()
    pva_port = free_localhost_port()
    pva_bcast = free_localhost_port()
    pinned = {
        # CA env (Stage-1c): server + client both pinned to a single port
        "EPICS_CA_SERVER_PORT": str(ca_port),
        "EPICS_CAS_INTF_ADDR_LIST": "127.0.0.1",
        "EPICS_CAS_BEACON_ADDR_LIST": "127.0.0.1",
        "EPICS_CAS_AUTO_BEACON_ADDR_LIST": "NO",
        "EPICS_CA_ADDR_LIST": f"127.0.0.1:{ca_port}",
        "EPICS_CA_AUTO_ADDR_LIST": "NO",
        # PVA env (Stage-1d): server's TCP port + UDP broadcast pinned;
        # client's ADDR_LIST is loopback host only (NO port) so it
        # broadcasts to the server's bound UDP port to discover the
        # TCP service.
        "EPICS_PVAS_INTF_ADDR_LIST": "127.0.0.1",
        "EPICS_PVAS_SERVER_PORT": str(pva_port),
        "EPICS_PVAS_BROADCAST_PORT": str(pva_bcast),
        "EPICS_PVA_ADDR_LIST": "127.0.0.1",
        "EPICS_PVA_AUTO_ADDR_LIST": "NO",
        "EPICS_PVA_BROADCAST_PORT": str(pva_bcast),
    }
    original: dict[str, str | None] = {k: os.environ.get(k) for k in pinned}
    os.environ.update(pinned)
    try:
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture(scope="module")
def softioc(tmp_path_factory: pytest.TempPathFactory) -> Generator[str]:
    """Spawn one `epicscorelibs.ioc` subprocess per test module; yield the PV prefix.

    Module scope amortizes ~1-2s of softIOC startup across many tests
    in the same file. Per-test isolation comes from
    `_purge_aioca_caches` (channel-cache reset between tests on the
    same subprocess).

    PV prefix carries a `uuid4()` fragment so two modules in the same
    worker can't collide; this also gives xdist-cross-worker collision
    safety as belt-and-braces (the per-worker port from
    `_pin_epics_env` already does the heavy lifting).

    Teardown uses `try/except BaseException` rather than plain `Exception`
    so a pytest-timeout `KeyboardInterrupt` (interrupt-main thread
    method per `feedback_pytest_timeout`) can't escape mid-shutdown
    leaving the subprocess as an orphan. `stop_softioc_cleanly`
    escalates exit -> SIGTERM -> SIGKILL.
    """
    prefix = f"cora_test_{uuid4().hex[:8]}:"
    log_dir = tmp_path_factory.mktemp(f"softioc_{uuid4().hex[:6]}")
    db_path = emit_db_file(log_dir)
    process = start_softioc(prefix, db_path, log_dir=log_dir)
    try:
        asyncio.run(wait_for_softioc_ready(prefix, log_dir=log_dir, deadline_s=5.0))
        yield prefix
    except BaseException:
        with contextlib.suppress(Exception):
            process.kill()
        raise
    finally:
        with contextlib.suppress(Exception):
            from aioca import purge_channel_caches

            purge_channel_caches()
        with contextlib.suppress(Exception):
            asyncio.run(stop_softioc_cleanly(process))


@pytest_asyncio.fixture(autouse=True)
async def _purge_aioca_caches(request: pytest.FixtureRequest) -> AsyncGenerator[None]:
    """Drop aioca channel caches after each test that touched the softIOC.

    Scoped via `softioc in request.fixturenames` so tests that don't
    use the softioc fixture (~99% of integration tests) skip the
    aioca import + purge call entirely. Without this guard, every
    Postgres-only integration test pays the import cost.

    For tests that DO use softioc: per the ophyd-async pattern,
    subscriptions registered during a test must be released before
    the function-scoped pytest-asyncio loop closes, otherwise the
    next test on a fresh loop sees `RuntimeError: Event loop is
    closed` errors as old subscriptions get garbage-collected.
    """
    yield
    if "softioc" not in request.fixturenames:
        return
    with contextlib.suppress(Exception):
        from aioca import purge_channel_caches

        purge_channel_caches()


@pytest_asyncio.fixture
async def db_pool(
    postgres_container: PostgresContainer,
    template_database: str,
) -> AsyncGenerator[asyncpg.Pool]:
    """Per-test database cloned from the migrated template; dropped at teardown."""
    test_db = f"t_{uuid4().hex[:12]}"
    admin_url = normalize_async_url(postgres_container.get_connection_url(), database="postgres")

    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'CREATE DATABASE "{test_db}" TEMPLATE "{template_database}"')
    finally:
        await admin.close()

    test_url = normalize_async_url(postgres_container.get_connection_url(), database=test_db)
    pool = await create_pool(test_url, min_size=1, max_size=4)
    try:
        yield pool
    finally:
        await pool.close()
        admin = await asyncpg.connect(admin_url)
        try:
            await admin.execute(f'DROP DATABASE "{test_db}"')
        finally:
            await admin.close()
