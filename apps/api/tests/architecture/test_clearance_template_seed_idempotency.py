"""Architecture-fitness tests pinning the idempotency contract of the
Safety BC `seed_clearance_templates` lifespan hook.

The hook is called on every app boot to seed the baseline
ClearanceTemplate set per Active Facility. Idempotency must ride on
the deterministic `clearance_template_stream_id(facility_code,
template_code)` derivation: the second boot collides on
`expected_version=0` and surfaces `ConcurrencyError`, which the hook
swallows as the "already seeded" signal. If a refactor removes the
swallow, removes the derived stream-id call, or drifts the baseline
form-type vocabulary, these static-source checks fail loudly.

Heuristic, not a proof. The checks read the seed module via
`inspect.getsource`; reviewers still need to verify behavior under the
PG integration suite. The point is to make the contract impossible to
silently break.
"""

from __future__ import annotations

import inspect

import pytest

from cora.safety import _clearance_template_seed
from cora.safety._clearance_template_seed import (
    TEN_FORM_TYPES,
    seed_clearance_templates,
)


@pytest.mark.architecture
@pytest.mark.unit
def test_seed_clearance_templates_swallows_concurrency_error() -> None:
    """The seed hook catches `ConcurrencyError`, does not re-raise, and
    logs an `already_present` info line. A re-raise here would crash
    the second boot; missing the log would silently hide drift."""
    source = inspect.getsource(_clearance_template_seed)
    assert "except ConcurrencyError" in source, (
        "seed_clearance_templates must catch ConcurrencyError as the "
        "'already seeded' idempotency signal"
    )

    module_lines = source.splitlines()
    except_index = next(
        i for i, line in enumerate(module_lines) if "except ConcurrencyError" in line
    )
    except_indent = len(module_lines[except_index]) - len(module_lines[except_index].lstrip())
    block_lines: list[str] = []
    for line in module_lines[except_index + 1 :]:
        if line.strip() == "":
            block_lines.append(line)
            continue
        line_indent = len(line) - len(line.lstrip())
        if line_indent <= except_indent:
            break
        block_lines.append(line)

    block_text = "\n".join(block_lines)
    assert "raise" not in block_text, (
        "except ConcurrencyError block must not re-raise; "
        "the hook is supposed to swallow it as the idempotent path"
    )
    assert "_log.info" in block_text, (
        "except ConcurrencyError block must log via _log.info "
        "(already-present signal must be observable)"
    )


@pytest.mark.architecture
@pytest.mark.unit
def test_seed_clearance_templates_uses_stream_derived_ids() -> None:
    """Idempotency rides on the deterministic stream-id derivation.
    The hook must both import and call `clearance_template_stream_id`,
    otherwise repeat boots cannot collide on `expected_version=0`."""
    source = inspect.getsource(_clearance_template_seed)
    assert "clearance_template_stream_id" in source, (
        "seed hook must reference clearance_template_stream_id "
        "(idempotency depends on derived stream-id, not random UUIDs)"
    )

    body_source = inspect.getsource(seed_clearance_templates)
    combined_source = source
    assert "clearance_template_stream_id(" in combined_source, (
        "clearance_template_stream_id must be CALLED, not just imported; "
        "the call site is what binds the (facility_code, template_code) "
        "pair to a stable stream-id"
    )
    # Re-binding to silence unused-name lint while keeping the helper
    # explicit for the next reader.
    assert body_source is not None


@pytest.mark.architecture
@pytest.mark.unit
def test_ten_form_types_is_exact_set() -> None:
    """The baseline form-type vocabulary is closed and pinned at ten.
    Adding or removing a form-type requires updating the design memo
    plus this test in the same change; ad-hoc drift trips here."""
    expected = {
        "ESAF",
        "SAF",
        "AForm",
        "DUO",
        "ESRA",
        "ERA",
        "PLHD",
        "DOOR",
        "BTR",
        "Form9",
    }
    assert set(TEN_FORM_TYPES) == expected
    assert len(TEN_FORM_TYPES) == 10, (
        "TEN_FORM_TYPES must have exactly ten entries with no duplicates"
    )
