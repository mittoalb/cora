"""Every decider carries an ``Invariants:`` block listing its rejections.

Per ``docs/reference/patterns.md``:

  > Decider docstrings carry an ``Invariants:`` block listing each
  > rejection inline with its exception name. This is the contract;
  > downstream readers (test author, API consumer) shouldn't have to
  > re-derive it from the body.

Detection is **file-level**: the string ``"Invariants:"`` appears
anywhere in the decider's text (module docstring OR ``decide`` function
docstring). The patterns.md example shows the block inside the
function's docstring, but the older convention placed it in the module
docstring; both are accepted today. A future phase can tighten this to
the function-docstring-only form once the existing files are aligned.

``DECIDERS_MISSING_INVARIANTS`` is the explicit work-tracker for the
67 deciders that currently lack the block (per the 2026-05-22 audit).
Phase ζ adds the blocks one BC at a time and removes the matching
allowlist entries. The test fails BOTH ways: a missing decider that's
not allowlisted, AND an allowlisted decider that now has the block
(so the allowlist can't go stale).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import BCS, CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


# Generated from the 2026-05-22 audit + 2026-05-23 re-audit.
# Entries are removed as Phase ζ adds Invariants: blocks. Empty means
# 100% compliance and the allowlist can be deleted.
DECIDERS_MISSING_INVARIANTS: frozenset[str] = frozenset(
    {
        "cora.access.features.register_actor.decider",
        "cora.agent.features.define_agent.decider",
        "cora.agent.features.deprecate_agent.decider",
        "cora.agent.features.grant_tool_to_agent.decider",
        "cora.agent.features.promote_caution_proposal.decider",
        "cora.agent.features.resume_agent.decider",
        "cora.agent.features.revise_agent_budget.decider",
        "cora.agent.features.revoke_tool_from_agent.decider",
        "cora.agent.features.suspend_agent.decider",
        "cora.agent.features.version_agent.decider",
        "cora.calibration.features.append_revision.decider",
        "cora.calibration.features.define_calibration.decider",
        "cora.campaign.features.abandon_campaign.decider",
        "cora.campaign.features.add_run_to_campaign.decider",
        "cora.campaign.features.close_campaign.decider",
        "cora.campaign.features.hold_campaign.decider",
        "cora.campaign.features.register_campaign.decider",
        "cora.campaign.features.remove_run_from_campaign.decider",
        "cora.campaign.features.resume_campaign.decider",
        "cora.campaign.features.start_campaign.decider",
        "cora.caution.features.register_caution.decider",
        "cora.caution.features.retire_caution.decider",
        "cora.caution.features.supersede_caution.decider",
        "cora.data.features.demote_dataset.decider",
        "cora.data.features.promote_dataset.decider",
        "cora.data.features.register_dataset.decider",
        "cora.decision.features.rate_decision.decider",
        "cora.decision.features.register_decision.decider",
        "cora.equipment.features.add_asset_family.decider",
        "cora.equipment.features.add_asset_port.decider",
        "cora.equipment.features.define_family.decider",
        "cora.equipment.features.register_asset.decider",
        "cora.equipment.features.relocate_asset.decider",
        "cora.equipment.features.remove_asset_family.decider",
        "cora.equipment.features.remove_asset_port.decider",
        "cora.equipment.features.update_asset_settings.decider",
        "cora.operation.features.register_procedure.decider",
        "cora.operation.features.start_procedure.decider",
        "cora.recipe.features.add_plan_wire.decider",
        "cora.recipe.features.define_method.decider",
        "cora.recipe.features.define_plan.decider",
        "cora.recipe.features.define_practice.decider",
        "cora.recipe.features.remove_plan_wire.decider",
        "cora.recipe.features.update_plan_default_parameters.decider",
        "cora.run.features.adjust_run.decider",
        "cora.run.features.start_run.decider",
        "cora.safety.features.activate_clearance.decider",
        "cora.safety.features.amend_clearance.decider",
        "cora.safety.features.append_clearance_review_step.decider",
        "cora.safety.features.approve_clearance.decider",
        "cora.safety.features.expire_clearance.decider",
        "cora.safety.features.register_clearance.decider",
        "cora.safety.features.reject_clearance.decider",
        "cora.safety.features.start_clearance_review.decider",
        "cora.safety.features.submit_clearance.decider",
        "cora.subject.features.register_subject.decider",
        "cora.supply.features.degrade_supply.decider",
        "cora.supply.features.mark_supply_available.decider",
        "cora.supply.features.mark_supply_recovering.decider",
        "cora.supply.features.mark_supply_unavailable.decider",
        "cora.supply.features.register_supply.decider",
        "cora.supply.features.restore_supply.decider",
        "cora.trust.features.define_conduit.decider",
        "cora.trust.features.define_policy.decider",
        "cora.trust.features.define_surface.decider",
        "cora.trust.features.define_zone.decider",
    }
)


def _decider_files() -> list[Path]:
    tracked = tracked_python_files()
    out: list[Path] = []
    for bc in BCS:
        features = CORA_ROOT / bc / "features"
        out.extend(
            sorted(
                f
                for f in tracked
                if f.name == "decider.py"
                and f.parent.parent == features
                and not f.parent.name.startswith("_")
            )
        )
    return out


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


@pytest.mark.architecture
@pytest.mark.parametrize("decider", _decider_files(), ids=_qualified)
def test_decider_carries_invariants_block(decider: Path) -> None:
    qualified = _qualified(decider)
    has_invariants = "Invariants:" in decider.read_text()
    in_allowlist = qualified in DECIDERS_MISSING_INVARIANTS

    if in_allowlist:
        assert not has_invariants, (
            f"{qualified}: now has `Invariants:` block; remove from "
            "DECIDERS_MISSING_INVARIANTS in test_decider_docstring_invariants_block.py."
        )
    else:
        assert has_invariants, (
            f"{qualified}: decider missing `Invariants:` block. "
            "Per docs/reference/patterns.md, every decider docstring "
            "enumerates rejections inline with each exception name."
        )


@pytest.mark.architecture
def test_allowlisted_deciders_actually_exist() -> None:
    """``DECIDERS_MISSING_INVARIANTS`` entries must point at real files."""
    for qualified in DECIDERS_MISSING_INVARIANTS:
        parts = qualified.split(".")
        assert parts[0] == "cora", f"{qualified}: must start with 'cora.'"
        path = CORA_ROOT.joinpath(*parts[1:]).with_suffix(".py")
        assert path.is_file(), (
            f"DECIDERS_MISSING_INVARIANTS entry {qualified} no longer exists; remove it"
        )
