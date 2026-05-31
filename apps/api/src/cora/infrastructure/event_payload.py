"""Stored-event payload deserialization helper.

Hoisted after the 28th `from_stored` shipped 162 inline
`except (KeyError, TypeError, AttributeError)` wrap sites that
re-raise as `ValueError("Malformed {event_type} payload ...")`.

Why a free function (not a decorator or base class)
---------------------------------------------------
Each per-aggregate `from_stored` is a `match stored.event_type:`
dispatch where each arm builds an event dataclass. The shared
shape across all 162 sites is the **try / wrap / re-raise** body,
not the dispatch or the builder expression itself. A free function
lets each `case "X":` arm stay a one-line call:

    case "ActorRegisteredV2":
        return deserialize_or_raise(
            "ActorRegisteredV2",
            lambda: ActorRegistered(
                actor_id=UUID(payload["actor_id"]),
                occurred_at=datetime.fromisoformat(payload["occurred_at"]),
                kind=ActorKind(payload["kind"]),
            ),
            extra=(ValueError,),
        )

A decorator on the case arm is impossible (Python match-case arms
cannot be decorated). A base class would force every aggregate's
event union through an inheritance chain for zero structural
benefit. The free-function form keeps each arm legible inside the
existing `match` body.

Why `extra` is a keyword tuple
------------------------------
Six call sites need to additionally catch `ValueError` raised by
inline `Enum(payload[k])` calls (ActorKind, SurfaceKind, Direction,
AbiTier). The default empty tuple matches the 156-site majority;
the 6 sites pass `extra=(ValueError,)`.

Why the payload is NOT echoed in the message
--------------------------------------------
The legacy per-site message was
`f"Malformed {event_type} payload {payload!r}: {exc}"`. Echoing the
raw payload into a `ValueError` string leaks fields into
log aggregators (Sentry, Datadog) that may correlate against
the PII-vault `actor_profile` rows. The architecture fitness at
`tests/architecture/test_from_stored_wraps_payload.py` asserts only
the `"Malformed {event_type} payload"` substring; no unit test
asserts on the echo. Dropping the echo is fitness-safe and
log-hygienic.

Why `message_suffix` is keyword-only
------------------------------------
Exactly one call site (Actor's `ActorRegistered` V1 arm) carries a
` (V1)` suffix in the legacy message to distinguish it from the
modern `ActorRegisteredV2` arm. The suffix is placed AFTER the
`payload` token so the fitness substring (`Malformed
ActorRegistered payload`) survives unchanged.
"""

from collections.abc import Callable


def deserialize_or_raise[EventT](
    event_type: str,
    builder: Callable[[], EventT],
    *,
    extra: tuple[type[BaseException], ...] = (),
    message_suffix: str = "",
) -> EventT:
    """Run `builder` and re-raise stored-event decoding failures as `ValueError`.

    Catches `KeyError`, `TypeError`, `AttributeError`, plus any
    classes in `extra`; re-raises a `ValueError` carrying the
    canonical `"Malformed {event_type} payload{message_suffix}: {exc}"`
    text. The original exception is chained via `__cause__`.

    The raw payload is intentionally NOT included in the message;
    see module docstring for the PII-hygiene rationale.
    """
    try:
        return builder()
    except (KeyError, TypeError, AttributeError, *extra) as exc:
        msg = f"Malformed {event_type} payload{message_suffix}: {exc}"
        raise ValueError(msg) from exc


__all__ = ["deserialize_or_raise"]
