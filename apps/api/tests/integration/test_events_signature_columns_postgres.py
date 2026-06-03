"""Integration tests: events.signature + events.signature_kid columns.

Pins the schema-level invariants introduced by the
`20260523214753_add_events_signature_columns.sql` migration:

  - Both columns nullable; NULL is the legitimate pre-rollout marker.
  - CHECK constraint `events_signature_kid_consistency` enforces
    both-null-or-both-set; a half-set row is rejected at INSERT.

The handler-side wiring that POPULATES these columns lands in a future
iteration (per `project_signed_events_design` scope split); this test
just proves the substrate behaves correctly under raw SQL.
"""

from __future__ import annotations

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from uuid import uuid4

import asyncpg
import pytest


async def _insert_event(
    pool: asyncpg.Pool,
    *,
    signature: bytes | None,
    signature_kid: str | None,
    signature_version: str | None = None,
) -> None:
    """Insert one minimal event row with the given signature shape.

    `signature_version` follows the matched-pair invariant on the
    events table: it must be set iff `signature` is set. Defaults
    to "cora/v1" when `signature` is non-None and no explicit version
    was passed, so existing tests focused on the signature/kid pair
    stay valid without per-call boilerplate.
    """
    if signature is not None and signature_version is None:
        signature_version = "cora/v1"
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO events (
                event_id, stream_type, stream_id, version, event_type,
                payload, correlation_id, occurred_at,
                signature, signature_kid, signature_version
            ) VALUES (
                $1, 'TestStream', $2, 1, 'TestEvent',
                '{}'::jsonb, $3, now(),
                $4, $5, $6
            )
            """,
            uuid4(),
            uuid4(),
            uuid4(),
            signature,
            signature_kid,
            signature_version,
        )


@pytest.mark.integration
async def test_events_accepts_both_null_signature_columns(
    db_pool: asyncpg.Pool,
) -> None:
    """Pre-rollout shape: legacy events have NULL in both columns.
    Forward-only migration policy forbids backfill, so this is the
    immortal default for events that landed before signing existed."""
    await _insert_event(db_pool, signature=None, signature_kid=None)


@pytest.mark.integration
async def test_events_accepts_both_set_signature_columns(
    db_pool: asyncpg.Pool,
) -> None:
    """Signed shape: future Caution and Decision handlers populate
    both columns when an AI-agent event lands."""
    signature = b"\x01" * 64
    await _insert_event(db_pool, signature=signature, signature_kid="kid-test")


@pytest.mark.integration
async def test_events_rejects_signature_without_kid(db_pool: asyncpg.Pool) -> None:
    """Half-set rows are a write-side bug: a signature without its kid
    cannot be verified. CHECK constraint catches it at INSERT before
    the row lands; an immortal half-signed row would silently fail
    verification at audit time."""
    with pytest.raises(asyncpg.CheckViolationError) as exc_info:
        await _insert_event(db_pool, signature=b"\x01" * 64, signature_kid=None)
    assert "events_signature_kid_consistency" in str(exc_info.value)


@pytest.mark.integration
async def test_events_rejects_kid_without_signature(db_pool: asyncpg.Pool) -> None:
    """The symmetric half-set: a kid without bytes to verify against."""
    with pytest.raises(asyncpg.CheckViolationError) as exc_info:
        await _insert_event(db_pool, signature=None, signature_kid="kid-orphan")
    assert "events_signature_kid_consistency" in str(exc_info.value)


@pytest.mark.integration
async def test_events_rejects_signature_with_wrong_byte_length(
    db_pool: asyncpg.Pool,
) -> None:
    """Ed25519 signatures are exactly 64 bytes per RFC 8032. A 63-
    or 65-byte signature is structurally invalid; rejecting it at
    the schema layer prevents a buggy adapter from polluting the
    immortal events table with bytes that can never verify."""
    with pytest.raises(asyncpg.CheckViolationError) as exc_info:
        await _insert_event(db_pool, signature=b"\x01" * 63, signature_kid="kid-x")
    assert "events_signature_length" in str(exc_info.value)
    with pytest.raises(asyncpg.CheckViolationError) as exc_info:
        await _insert_event(db_pool, signature=b"\x01" * 65, signature_kid="kid-x")
    assert "events_signature_length" in str(exc_info.value)


@pytest.mark.integration
async def test_events_rejects_empty_signature_kid(db_pool: asyncpg.Pool) -> None:
    """An empty kid alongside a real signature is meaningless: the
    verifier has nothing to resolve to a public key. Reject at write
    time rather than letting an unverifiable row land."""
    with pytest.raises(asyncpg.CheckViolationError) as exc_info:
        await _insert_event(db_pool, signature=b"\x01" * 64, signature_kid="")
    assert "events_signature_kid_length" in str(exc_info.value)


@pytest.mark.integration
async def test_events_rejects_excessively_long_signature_kid(
    db_pool: asyncpg.Pool,
) -> None:
    """256-char ceiling on the kid prevents a buggy or compromised
    adapter from polluting the immortal table with arbitrary-length
    opaque strings. 256 chars comfortably fits Sigstore Fulcio cert
    serials, SPIFFE IDs, and KMS resource names."""
    with pytest.raises(asyncpg.CheckViolationError) as exc_info:
        await _insert_event(db_pool, signature=b"\x01" * 64, signature_kid="x" * 257)
    assert "events_signature_kid_length" in str(exc_info.value)
