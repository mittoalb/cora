"""Integration-test fixtures: per-test Postgres database + caproto IOC.

The session-scoped `postgres_container` and `template_database`
fixtures live in `tests/conftest.py` so the e2e tier can share them.
This module adds:

- `db_pool`: per-test database cloned via `CREATE DATABASE ...
  TEMPLATE migrated_db` (file-copy fast, full isolation, no TRUNCATE
  bookkeeping).
- `caproto_ioc`: per-test in-process EPICS CA IOC on an ephemeral
  port for the Stage-1b `CaprotoControlPort` integration tests. xdist
  workers cannot clash because each test gets its own ephemeral
  loopback port; env vars (`EPICS_CA_*`, `EPICS_CAS_*`) are scoped
  via `monkeypatch`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false

import asyncio
import contextlib
import os
import socket
from collections.abc import AsyncGenerator
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from caproto.asyncio.server import start_server
from testcontainers.postgres import PostgresContainer

from cora.infrastructure.postgres.pool import create_pool
from tests._postgres import normalize_async_url
from tests.integration._caproto_ioc import CoraTestIOC


def _free_localhost_port() -> int:
    """Allocate a free loopback port. Bind-and-close idiom; the kernel
    reuses freed ports immediately, and concurrent xdist workers each
    get a distinct port because the kernel never reissues an in-use one.
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest_asyncio.fixture
async def caproto_ioc(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[str]:
    """Boot a `CoraTestIOC` on an ephemeral loopback port; yield the PV prefix.

    Lifecycle:
      1. Allocate a free loopback port.
      2. Lock client + server EPICS env vars onto `127.0.0.1:<port>` via
         monkeypatch (test scope) so concurrent xdist workers cannot collide.
      3. Construct `CoraTestIOC(prefix=...)` with a per-test prefix
         (PID + port baked in; collision-proof within a worker).
      4. Spawn `caproto.asyncio.server.start_server` in a background
         task; the CLI `run()` would install signal handlers and
         block the event loop, useless for a fixture.
      5. Poll the TCP port via short connect attempts until the server
         is accepting (or a 5s deadline elapses). Replaces a hardcoded
         `asyncio.sleep` so a slow CI worker (xdist `-n 4` + Postgres
         testcontainers competing for CPU) doesn't manifest as a flake.
      6. Yield the prefix.
      7. Cancel the task; suppress the resulting `CancelledError`.
    """
    port = _free_localhost_port()
    prefix = f"cora_test_{os.getpid()}_{port}:"

    monkeypatch.setenv("EPICS_CA_SERVER_PORT", str(port))
    monkeypatch.setenv("EPICS_CAS_INTF_ADDR_LIST", "127.0.0.1")
    monkeypatch.setenv("EPICS_CAS_BEACON_ADDR_LIST", "127.0.0.1")
    monkeypatch.setenv("EPICS_CAS_AUTO_BEACON_ADDR_LIST", "NO")
    monkeypatch.setenv("EPICS_CA_ADDR_LIST", f"127.0.0.1:{port}")
    monkeypatch.setenv("EPICS_CA_AUTO_ADDR_LIST", "NO")

    ioc = CoraTestIOC(prefix=prefix)
    task = asyncio.create_task(start_server(ioc.pvdb, interfaces=["127.0.0.1"]))

    await _wait_for_caproto_ioc_ready(port, deadline_s=5.0)

    try:
        yield prefix
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def _wait_for_caproto_ioc_ready(port: int, *, deadline_s: float) -> None:
    """Poll the loopback TCP port until the caproto IOC is accepting.

    Replaces a fixed `asyncio.sleep` so slow CI workers (xdist plus
    Postgres testcontainers competing for CPU) don't manifest as a
    flake. 5s is generous; production loopback warmup is ~50ms.
    """
    deadline = asyncio.get_event_loop().time() + deadline_s
    while asyncio.get_event_loop().time() < deadline:
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
        except (ConnectionRefusedError, OSError):
            await asyncio.sleep(0.02)
            continue
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
        _ = reader
        return
    msg = f"caproto IOC on 127.0.0.1:{port} did not accept within {deadline_s}s"
    raise RuntimeError(msg)


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
