"""Enforce the consistency-lock rule: no phase / iter / audit markers in src/.

Codified in `docs/reference/conventions.md#documentation`:

> Do not name a phase, iteration, or audit (`Phase 5h`, `Iter B-3`,
> `DLM-A`, `audit-2026-...`) in a docstring or comment. Those rot.
> The current code is what's true; phase ordering lives in
> `project_phase_plan.md` and git history.

This fitness function walks every tracked `.py` file under `src/cora`
and fails on any line carrying a forbidden marker, except for a small
allowlist of substantive non-marker uses (e.g. the ISA-88 domain
noun "Phase" capitalized as a concept name, or wiki-link references
to design-memo filenames that happen to encode a phase number).

The forbidden patterns and the rationale for each:

  - `Phase <digit-or-letter>...` — chronological marker that rots
    (the project's phase labels are an internal scaffold).
  - `Iter [A-Z]...` — sub-phase iteration marker.
  - `DLM-[A-Z]` — design-lock-memo internal identifier.
  - `audit-YYYY-MM-DD` — audit-cohort tag (the audit ran once; the
    finding is now the present-tense state).

## Allowed uses (false positives we explicitly skip)

  - "Phase IS a Procedure" (and similar capitalized-as-domain-noun
    uses) — the ISA-88 / ISA-106 Phase concept is a real DDD term
    in `cora.operation.aggregates.procedure.state`. The regex would
    match `Phase I` because `I` is `[A-Z]`; we filter those.
  - Wiki-link references to design memos with phase-numbered slugs
    like `[[family-affordance-design-phases-5i-5j-lock]]` — memo
    filenames are external and not in scope for this rule.

This test is the durable guardrail; without it phase markers
re-accumulate at every PR.
"""

import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path

# Forbidden patterns. Each must MATCH on a line to be a violation; we
# then run per-line filters to suppress known-good occurrences.
_FORBIDDEN = re.compile(
    r"Phase [0-9A-Z]"  # Phase 5h, Phase A, Phase 12c-2, Phase IS-domain-noun
    r"|"
    r"\bIter [A-Z]\b"  # Iter A, Iter B-3
    r"|"
    r"DLM-[A-Z]"  # DLM-A, DLM-B
    r"|"
    r"audit-[0-9]{4}-[0-9]{2}-[0-9]{2}"  # audit-2026-05-20
)

# The ISA-88 / ISA-106 "Phase" domain noun (capitalized common-English
# word) shows up legitimately in the Operation BC's Procedure aggregate
# docstring. The forbidden regex matches `Phase I...` because `I` is
# in `[A-Z]`; this allowlist tells the test that those specific uses
# are domain vocabulary, not phase markers.
_DOMAIN_PHASE_WORDS = re.compile(
    r"\bPhase (IS|aggregate|concept)\b"  # "Phase IS a Procedure", "Phase aggregate"
)

# Wiki-link references to design memo filenames are out of scope.
# Memo slugs that happen to encode phase numbers (e.g.
# `family-affordance-design-phases-5i-5j-lock`) are external to this
# codebase and not in scope for the consistency-lock rule.
_WIKI_LINK = re.compile(r"\[\[[^\]]+\]\]")


def _violations_for_line(line: str) -> str | None:
    """Return None if the line is allowed; otherwise the matched substring."""
    # Strip wiki-link references first — anything inside `[[...]]` is
    # outside the rule's scope.
    stripped = _WIKI_LINK.sub("", line)
    match = _FORBIDDEN.search(stripped)
    if match is None:
        return None
    # Check whether the match is a domain-noun usage.
    span = match.group(0)
    if span.startswith("Phase ") and _DOMAIN_PHASE_WORDS.search(stripped):
        # The match is on a line that also contains a domain-noun usage.
        # Confirm the specific match is the domain noun by re-checking
        # the surrounding capture rather than another Phase-marker on
        # the same line.
        domain_match = _DOMAIN_PHASE_WORDS.search(stripped)
        if domain_match and domain_match.start() == match.start():
            return None
    return span


@pytest.mark.architecture
def test_no_phase_markers_in_src() -> None:
    """Every tracked .py under src/cora is free of phase / iter / audit markers."""
    violations: list[tuple[Path, int, str, str]] = []
    for path in sorted(tracked_python_files()):
        if not path.is_relative_to(CORA_ROOT):
            continue
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = _violations_for_line(line)
            if match is not None:
                violations.append(
                    (path.relative_to(CORA_ROOT.parent.parent), lineno, match, line.rstrip())
                )

    if not violations:
        return

    msg_lines = [
        f"Found {len(violations)} phase / iter / audit marker(s) in src/cora.",
        "These rot. See docs/reference/conventions.md#documentation for the rule.",
        "",
    ]
    for path, lineno, match, line in violations[:20]:
        msg_lines.append(f"  {path}:{lineno}: matched {match!r}")
        msg_lines.append(f"    {line}")
    if len(violations) > 20:
        msg_lines.append(f"  ... and {len(violations) - 20} more")
    pytest.fail("\n".join(msg_lines))
