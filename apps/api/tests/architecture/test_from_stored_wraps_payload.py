"""Every aggregate's `from_stored` wraps deserialization errors uniformly.

Convention adopted after the 2026-05-18 corpus survey (Marten,
pyeventsourcing, Pydantic, msgspec, cattrs all wrap):

    case "EventType":
        try:
            return EventType(
                field=UUID(payload["field"]),
                ...
            )
        except (KeyError, TypeError, AttributeError) as exc:
            msg = f"Malformed EventType payload {payload!r}: {exc}"
            raise ValueError(msg) from exc

Rationale: a corrupted event row should fail loud with the event-type
name in the error message, not bubble a raw `KeyError('agent_id')` from
deep in the load path. Sentry/Datadog group by exception type + top
frame; without the wrap, every aggregate's KeyError collapses into one
undifferentiated issue. `from exc` preserves the original traceback so
nothing is lost.

This test reads each `events.py`'s `from_stored` body, finds every
`case "X":` clause, and asserts the literal `Malformed X payload`
string appears in the body. Idempotent and AST-shape-agnostic; works
whether the wrap is per-case inline or hoisted into a helper later.
"""

import re
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT


def _aggregate_events_files() -> list[Path]:
    """All `events.py` files under `<bc>/aggregates/<agg>/events.py`."""
    return sorted(CORA_ROOT.glob("*/aggregates/*/events.py"))


def _qualified(p: Path) -> str:
    rel = p.relative_to(CORA_ROOT)
    return "cora." + ".".join(rel.with_suffix("").parts)


def _from_stored_body(text: str) -> str | None:
    """Extract the `from_stored` function body, stopping at the next
    top-level `def` or `__all__`."""
    pattern = r"^def from_stored.*?(?=^def [^_]|^__all__|^class )"
    m = re.search(pattern, text, re.DOTALL | re.MULTILINE)
    return m.group() if m else None


@pytest.mark.architecture
@pytest.mark.parametrize("events_file", _aggregate_events_files(), ids=_qualified)
def test_from_stored_wraps_every_event_type(events_file: Path) -> None:
    """Each `case "X":` arm in `from_stored` must have a matching
    `Malformed X payload` wrap message in the function body."""
    text = events_file.read_text()
    body = _from_stored_body(text)
    if body is None:
        pytest.skip(f"{_qualified(events_file)}: no from_stored function")

    case_names = list(dict.fromkeys(re.findall(r'case "(\w+)":', body)))
    if not case_names:
        pytest.skip(f"{_qualified(events_file)}: no event-type cases found")

    unwrapped = [n for n in case_names if f"Malformed {n} payload" not in body]
    assert not unwrapped, (
        f"{_qualified(events_file)}: the following event-type cases in "
        f"from_stored() do not wrap KeyError/TypeError/AttributeError as "
        f'`raise ValueError("Malformed <EventType> payload ...")`: {unwrapped}.\n'
        f"\nSee tests/architecture/test_from_stored_wraps_payload.py for the "
        f"convention rationale + corpus survey. Apply the same per-case "
        f"try/except wrap used by the already-converted aggregates."
    )
