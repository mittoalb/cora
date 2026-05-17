"""Shared payload extractors for subscribers that react to terminal Run events.

Hoisted at rule-of-three (two consumers today, third agent named
in the iter-4 widening triggers). Only the OBVIOUSLY-stable
extractors live here; the `_compose_and_append` Decision-event
composer remains duplicated across `run_debrief` and
`caution_drafter` until iter 4 reveals which seams stabilize
(per the post-review simplification audit: deferred composer hoist
to avoid premature parameter-shuffler).

Both extractors are pure (no IO, no I/O ports) and `None`-tolerant:
new terminal event shapes (future) don't crash the consumer when
they omit one of these optional fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cora.infrastructure.ports.event_store import StoredEvent


def extract_reason(event: StoredEvent) -> str | None:
    """Pull the `reason` field from a terminal-Run event payload.

    `RunCompleted` has no `reason`; the other three (`RunAborted`,
    `RunStopped`, `RunTruncated`) carry it. Returns `None` when
    missing rather than KeyError-raising.
    """
    reason = event.payload.get("reason")
    return str(reason) if reason is not None else None


def extract_interrupted_at(event: StoredEvent) -> str | None:
    """Pull `interrupted_at` from a terminal-Run event payload.

    `RunTruncated`-only field; absent on every other terminal type.
    """
    interrupted_at = event.payload.get("interrupted_at")
    return str(interrupted_at) if interrupted_at is not None else None


__all__ = ["extract_interrupted_at", "extract_reason"]
