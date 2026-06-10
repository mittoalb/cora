"""The `DefineClearanceTemplate` command  --  intent dataclass for this slice.

Carries only what the caller controls (the template's code, title, facility,
and an optional external reference). Server-side concerns (new aggregate id,
wall-clock timestamp, correlation id, per-event ids) are injected by the
handler from infrastructure ports.

Status is implicit at definition (`Draft`) and not part of the command;
see the ClearanceTemplate aggregate's `state.py` docstring for the
enum-in-state, str-in-event convention per [[project_defined_vs_registered_genesis]].

`version` is always 1 at genesis (set by the decider). Version chaining
lands in 9B's `version_clearance_template` slice with proper same-facility
parent validation; the genesis command does not accept `supersedes_template_id`
to avoid recording unverified parent claims in immutable events.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DefineClearanceTemplate:
    """Define a new safety clearance template with the given code and title."""

    code: str
    title: str
    facility_code: str
    external_ref: str | None = None
