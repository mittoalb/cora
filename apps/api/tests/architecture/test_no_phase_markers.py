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
    (the project's phase labels are an internal scaffold). Covers
    Latin forms (`Phase 5h`, `Phase B`), Greek-glyph forms
    (`Phase <alpha-glyph>`, `Phase <omega-glyph>`), and the English
    transliterations the team actually types in source
    (`Phase alpha` ... `Phase omega`); later project_phase_plan.md
    cohorts shifted to the Greek alphabet and the rule extends with
    them.
  - `Iter [A-Z]...` sub-phase iteration marker.
  - `DLM-[A-Z]` design-lock-memo internal identifier.
  - `audit-YYYY-MM-DD` audit-cohort tag (the audit ran once; the
    finding is now the present-tense state).
  - `P<n>-<Section>-<n>` gate-review section tag (`P0-Sec-2`,
    `P2-Design-3`); the bare `P<n>#<n>` priority-issue form is
    caught by a separate arm.
  - `Stage <n><letter>` and `Stage-<n><letter>` planning markers
    (`Stage 2a`, `Stage 2c-credential`, `Stage-1c`, `Stage 3b`);
    the optional `-<lowercase-suffix>` arm catches the
    sub-stage-with-name forms.

## Allowed uses (false positives we explicitly skip)

  - "Phase IS a Procedure" (and similar capitalized-as-domain-noun
    uses): the ISA-88 / ISA-106 Phase concept is a real DDD term
    in `cora.operation.aggregates.procedure.state`. The regex would
    match `Phase I` because `I` is `[A-Z]`; we filter those.
  - Wiki-link references to design memos with phase-numbered slugs
    like `[[family-affordance-design-phases-5i-5j-lock]]` or
    `[[stage-2a-foo]]`: memo filenames are external and not in
    scope for this rule. The `_WIKI_LINK` strip removes the entire
    `[[...]]` span before the forbidden-pattern search, so any
    lowercase, hyphenated, bracket-bounded stage slug inside a
    wiki-link is invisible to the check.
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
    # Latin-form phase tags: `Phase 5h`, `Phase B`.
    r"Phase [0-9A-Z]"
    r"|"
    # Greek-letter phase tags. Covers the lowercase alpha-omega block
    # (U+03B1-U+03C9, including final sigma U+03C2) and uppercase
    # Alpha-Omega (U+0391-U+03A9). project_phase_plan.md cohorts past
    # the Latin alphabet shifted to Greek; this arm catches the drift.
    # Code-point escapes (not literal glyphs) so RUF001 stays clean.
    "Phase [\u0391-\u03a9\u03b1-\u03c9]"
    r"|"
    # English transliterations of the Greek letters above. The team types
    # `Phase alpha` / `Phase delta` more often than the glyph form; the
    # Greek-glyph arm alone misses every spelled-out occurrence, which is
    # the drift class that accumulates in practice.
    r"Phase (?:alpha|beta|gamma|delta|epsilon|zeta|eta|theta|iota|"
    r"kappa|lambda|mu|nu|xi|omicron|pi|rho|sigma|tau|upsilon|phi|"
    r"chi|psi|omega)\b"
    r"|"
    r"\bIter [A-Z]\b"
    r"|"
    r"DLM-[A-Z]"
    r"|"
    r"audit-[0-9]{4}-[0-9]{2}-[0-9]{2}"
    r"|"
    # Gate-review section/priority tag like `P0-Sec-2`, `P2-Design-3`,
    # `P1-Impl-4`. The numeric-only `P1#3` form is caught by the
    # priority-issue arm further below; this catches the section-name
    # form that lives in design-memo bodies.
    r"\bP[0-9]+-[A-Z][a-z]+-[0-9]+\b"
    r"|"
    # Capitalized planning marker `Stage 2a`, `Stage-1c`, `Stage 3b`,
    # plus the sub-stage-with-name forms (`Stage 2c-credential`,
    # `Stage-2c-seal`). The trailing `(?:-[a-z]+)?` is optional so the
    # bare digit-letter form still matches. Wiki-link-bounded slugs
    # like `[[stage-2a-foo]]` are case-skipped by `_WIKI_LINK` before
    # this regex sees the line.
    r"\bStage[ -][0-9][a-z]?(?:-[a-z]+)?\b"
    r"|"
    # Implicit phase reference: prep word followed by a hyphenated phase
    # tag like `pre-7e`, `post-6g-c`, `from 6f-1`, `in 11a-c-3`. The
    # first chunk is bounded to 1-2 letters so directory paths like
    # `(in 2bmb-bin)` (a beamline binary folder) don't trip the rule.
    # Standalone single-letter forms (`5h`, `4f`) are too easily confused
    # with time units (`1h`, `30s`) and are handled by reviewer eyes,
    # not this regex.
    r"\b(?:pre|post|from|since|after|before|in|at)[ -][0-9]+[a-z]{1,2}-[a-z0-9]+\b"
    r"|"
    # Hyphenated phase tag opened by `pre-` / `post-` even without a
    # further hyphenated suffix: `pre-12c`, `post-6g`, `pre-7e`.
    r"\b(?:pre|post)-[0-9]+[a-z]{1,2}\b"
    r"|"
    # Lowercase iteration marker that escaped the capitalized form:
    # `iter 1`, `iter 2b`, `iter 3`.
    r"\biter [0-9][a-z]?\b"
    r"|"
    # Gate-review priority/issue reference: `P1#3`, `P0#6`.
    r"\bP[0-9]+#[0-9]+\b"
    r"|"
    # Anti-hook reference from design-lock memos: `AH4`, `AH14`.
    r"\bAH[0-9]+\b"
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
@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # Stage arm: bare digit + lowercase letter.
        ("Stage 2a holds the wiring.", "Stage 2a"),
        # Stage arm: hyphenated form (`Stage-1c`).
        ("Stage-1c production CA adapter.", "Stage-1c"),
        # Stage arm: digit-letter-name suffix.
        ("Stage 2c-credential lands the rotation slices.", "Stage 2c-credential"),
        # Stage arm: bare digit (no letter).
        ("Picked per Stage 0 corpus survey.", "Stage 0"),
    ],
)
def test_stage_arm_matches_planning_markers(line: str, expected: str) -> None:
    """The Stage arm catches both spaced and hyphenated planning markers."""
    assert _violations_for_line(line) == expected


@pytest.mark.architecture
@pytest.mark.parametrize(
    "line",
    [
        # Wiki-link slug containing a stage tag is stripped before search.
        "See [[stage-2a-foo]] for the lock.",
        "Refer to [[project-control-port-design]] (no stage tag).",
        # Capitalized "Stage" outside the marker shape (no digit) is fine.
        "Stage left to drop off the prop.",
        # Domain noun: ISA-88 Phase is allowed.
        "Phase IS a Procedure in ISA-88 terms.",
    ],
)
def test_allowed_lines_are_not_flagged(line: str) -> None:
    """Wiki-link-bounded stage slugs and non-marker uses must not trip the regex."""
    assert _violations_for_line(line) is None


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
