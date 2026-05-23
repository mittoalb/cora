"""Enforce the consistency-lock rule: no phase / iter / audit markers in tracked source.

Codified in `docs/reference/conventions.md#documentation`:

> Do not name a phase, iteration, or audit (`Phase 5h`, `Iter B-3`,
> `DLM-A`, `audit-2026-...`) in a docstring or comment. Those rot.
> The current code is what's true; phase ordering lives in
> `project_phase_plan.md` and git history.

This fitness function walks every tracked `.py` file under `src/cora`
AND under `tests/` and fails on any line carrying a forbidden marker,
except for a small allowlist of substantive non-marker uses (the
ISA-88 domain noun "Phase" capitalized as a concept name, and wiki-link
references to design-memo filenames that happen to encode a phase
number).

The forbidden patterns and the rationale for each:

  - `Phase <digit-or-letter>...` chronological marker that rots
    (the project's phase labels are an internal scaffold).
  - `Iter [A-Z]...` sub-phase iteration marker.
  - `DLM-[A-Z]` design-lock-memo internal identifier.
  - `audit-YYYY-MM-DD` audit-cohort tag (the audit ran once; the
    finding is now the present-tense state).

## Allowed uses (false positives we explicitly skip)

  - "Phase IS a Procedure" (and similar capitalized-as-domain-noun
    uses): the ISA-88 / ISA-106 Phase concept is a real DDD term
    in `cora.operation.aggregates.procedure.state`. The regex would
    match `Phase I` because `I` is `[A-Z]`; we filter those.
  - Wiki-link references to design memos with phase-numbered slugs
    like `[[family-affordance-design-phases-5i-5j-lock]]`: memo
    filenames are external and not in scope for this rule.
  - This file itself: it must name the forbidden patterns in its
    own regex and docstring. The walk skips it by basename.

This test is the durable guardrail; without it phase markers
re-accumulate at every PR.
"""

import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import tracked_python_files, tracked_test_files

if TYPE_CHECKING:
    from pathlib import Path

_FORBIDDEN = re.compile(
    r"Phase [0-9A-Z]"
    r"|"
    r"\bIter [A-Z]\b"
    r"|"
    r"DLM-[A-Z]"
    r"|"
    r"audit-[0-9]{4}-[0-9]{2}-[0-9]{2}"
)

_DOMAIN_PHASE_WORDS = re.compile(r"\bPhase (IS|aggregate|concept)\b")

_WIKI_LINK = re.compile(r"\[\[[^\]]+\]\]")

_SELF_FILENAME = "test_no_phase_markers.py"


def _violations_for_line(line: str) -> str | None:
    """Return None if the line is allowed; otherwise the matched substring."""
    stripped = _WIKI_LINK.sub("", line)
    match = _FORBIDDEN.search(stripped)
    if match is None:
        return None
    span = match.group(0)
    if span.startswith("Phase ") and _DOMAIN_PHASE_WORDS.search(stripped):
        domain_match = _DOMAIN_PHASE_WORDS.search(stripped)
        if domain_match and domain_match.start() == match.start():
            return None
    return span


@pytest.mark.architecture
def test_no_phase_markers_in_tracked_source() -> None:
    """Every tracked .py under src/cora and tests/ is free of phase / iter / audit markers."""
    violations: list[tuple[Path, int, str, str]] = []
    candidates = sorted(tracked_python_files() | tracked_test_files())
    for path in candidates:
        if path.name == _SELF_FILENAME:
            continue
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = _violations_for_line(line)
            if match is not None:
                violations.append((path, lineno, match, line.rstrip()))

    if not violations:
        return

    msg_lines = [
        f"Found {len(violations)} phase / iter / audit marker(s) in tracked source.",
        "These rot. See docs/reference/conventions.md#documentation for the rule.",
        "",
    ]
    for path, lineno, match, line in violations[:20]:
        msg_lines.append(f"  {path}:{lineno}: matched {match!r}")
        msg_lines.append(f"    {line}")
    if len(violations) > 20:
        msg_lines.append(f"  ... and {len(violations) - 20} more")
    pytest.fail("\n".join(msg_lines))
