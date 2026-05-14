"""Trimmed-bounded-text validation helper for value object `__post_init__`.

Originally hoisted in Phase 6e-1 as `validate_name` after the 10th
bounded-name VO landed (`PlanName`). Renamed to `validate_bounded_text`
post-domain-audit once the helper picked up 8 non-name callers (Run /
Subject / Dataset reason VOs + Decision choice/context/rule VOs) — the
shared concept across all 21 sites is "trimmed string with a bounded
length", not "name".

Why hoist a function (not a class)
-----------------------------------
The duplicated body across the call sites is the **trim + length-check
+ raise** logic, not the dataclass shape itself. Hoisting only the
validation function preserves what's worth keeping per-VO:

  - Distinct frozen dataclass type (`isinstance` checks stay
    aggregate-specific; pyright keeps `ActorName` and `MethodName`
    apart at type sites).
  - Distinct error class with aggregate-specific message text.
  - Per-VO `MAX_LENGTH` constant in the aggregate's state module
    (read by both the VO and the API-boundary Pydantic schema).

A `BoundedText` base class would couple all aggregates to one type
and make per-VO documentation harder to navigate. A class factory
would weaken `isinstance` semantics. A free function avoids both.

How VOs use it
--------------
The frozen-dataclass dance (`object.__setattr__` to install the
trimmed value) stays visible at the VO body so readers see the
constraint without chasing a helper.

    @dataclass(frozen=True)
    class ActorName:
        value: str

        def __post_init__(self) -> None:
            trimmed = validate_bounded_text(
                self.value,
                max_length=ACTOR_NAME_MAX_LENGTH,
                error_class=InvalidActorNameError,
            )
            object.__setattr__(self, "value", trimmed)

The error class's constructor is called with the **original**
(untrimmed) value so its message can quote what the caller actually
sent.
"""


def validate_bounded_text(
    value: str,
    *,
    max_length: int,
    error_class: type[Exception],
) -> str:
    """Trim, length-check, return the trimmed value, or raise `error_class`.

    Raises `error_class(value)` (the original untrimmed value) if the
    trimmed result is empty or exceeds `max_length`. Otherwise returns
    the trimmed string for the VO to install on itself.
    """
    trimmed = value.strip()
    if not trimmed or len(trimmed) > max_length:
        raise error_class(value)
    return trimmed


__all__ = ["validate_bounded_text"]
