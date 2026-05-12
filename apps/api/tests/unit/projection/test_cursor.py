"""Unit tests for the projection cursor encode/decode primitives."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.projection import (
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
)


@pytest.mark.unit
def test_round_trip_preserves_created_at_and_id() -> None:
    created_at = datetime(2026, 5, 12, 14, 30, 45, 123456, tzinfo=UTC)
    item_id = UUID("01900000-0000-7000-8000-00000000abcd")

    cursor = encode_cursor(created_at=created_at, item_id=item_id)
    decoded_at, decoded_id = decode_cursor(cursor)

    assert decoded_at == created_at
    assert decoded_id == item_id


@pytest.mark.unit
def test_round_trip_handles_microsecond_precision() -> None:
    """asyncpg returns timestamps with microsecond precision; the
    cursor must preserve it so keyset pagination doesn't double-fetch
    or skip rows at microsecond boundaries."""
    created_at = datetime(2026, 5, 12, 14, 30, 45, 999999, tzinfo=UTC)
    item_id = UUID("01900000-0000-7000-8000-00000000aaaa")

    decoded_at, _ = decode_cursor(encode_cursor(created_at=created_at, item_id=item_id))
    assert decoded_at.microsecond == 999999


@pytest.mark.unit
def test_encoded_cursor_is_url_safe() -> None:
    """Cursors travel in URL query strings; characters outside the
    URL-safe alphabet (`-`, `_`, alphanumerics) would need escaping."""
    cursor = encode_cursor(
        created_at=datetime(2026, 5, 12, tzinfo=UTC),
        item_id=UUID("01900000-0000-7000-8000-00000000abcd"),
    )
    safe_chars = set("-_") | set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    assert all(c in safe_chars for c in cursor)


@pytest.mark.unit
def test_decode_rejects_garbage() -> None:
    with pytest.raises(InvalidCursorError):
        decode_cursor("not-a-valid-cursor-at-all-!!!")


@pytest.mark.unit
def test_decode_rejects_missing_separator() -> None:
    """Cursor body without `|` separator is malformed."""
    import base64

    bad = base64.urlsafe_b64encode(b"no-separator-here").decode().rstrip("=")
    with pytest.raises(InvalidCursorError, match="separator"):
        decode_cursor(bad)


@pytest.mark.unit
def test_decode_rejects_malformed_timestamp() -> None:
    import base64

    bad_body = "not-a-timestamp|01900000-0000-7000-8000-00000000aaaa"
    bad = base64.urlsafe_b64encode(bad_body.encode()).decode().rstrip("=")
    with pytest.raises(InvalidCursorError, match="timestamp"):
        decode_cursor(bad)


@pytest.mark.unit
def test_decode_rejects_malformed_uuid() -> None:
    import base64

    bad_body = "2026-05-12T00:00:00+00:00|not-a-uuid"
    bad = base64.urlsafe_b64encode(bad_body.encode()).decode().rstrip("=")
    with pytest.raises(InvalidCursorError, match="UUID"):
        decode_cursor(bad)


@pytest.mark.unit
def test_invalid_cursor_error_carries_raw_input() -> None:
    """Helps log diagnostics; useful when a client reports the bad cursor."""
    raw = "totally-broken-cursor"
    try:
        decode_cursor(raw)
    except InvalidCursorError as exc:
        assert exc.raw == raw
    else:
        pytest.fail("InvalidCursorError not raised")
