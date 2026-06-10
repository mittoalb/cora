"""Closed-set fitness for the Role seed registry.

Per [[project-role-aggregate-design]] Q1 + Q3 (2026-06-10 user picks):
the 3A seed ships exactly 4 Roles (Imager, Positioner, Controller,
Detector); Conditioner is deferred. Every change to the seed list
fires this test, ensuring the closed-set claim is enforceable.

Federation portability requires deterministic UUID5 ids: every
deployment computes the same RoleId from the same name slug. This
test pins the four ids so an accidental namespace edit surfaces
immediately.
"""

from uuid import UUID

import pytest

from cora.equipment.aggregates.role import (
    CONTROLLER,
    DETECTOR,
    IMAGER,
    POSITIONER,
    SEED_ROLE_CONTROLLER_ID,
    SEED_ROLE_DETECTOR_ID,
    SEED_ROLE_IMAGER_ID,
    SEED_ROLE_POSITIONER_ID,
    SEED_ROLES,
)


@pytest.mark.unit
def test_seed_roles_closed_set_count_is_four() -> None:
    """3A ships exactly 4 seed Roles. Conditioner deferred (Q3)."""
    assert len(SEED_ROLES) == 4


@pytest.mark.unit
def test_seed_role_names_are_pinned() -> None:
    names = {role.name.value for role in SEED_ROLES}
    assert names == {"Imager", "Positioner", "Controller", "Detector"}


@pytest.mark.unit
def test_seed_role_ids_are_pinned_uuid5() -> None:
    """Federation-portable: every deployment computes the same RoleId."""
    assert UUID("156bdf22-ccdc-5dda-ad55-67c84d798b5e") == SEED_ROLE_IMAGER_ID
    assert UUID("0122b7e1-2724-5d5b-a62c-318c4c97a4e1") == SEED_ROLE_POSITIONER_ID
    assert UUID("3fee7782-7e89-50ba-a8e0-e9692348d2c2") == SEED_ROLE_CONTROLLER_ID
    assert UUID("7ae3449f-72b1-5182-8cc5-ff7d8adf2f9e") == SEED_ROLE_DETECTOR_ID


@pytest.mark.unit
def test_seed_role_ids_are_pairwise_distinct() -> None:
    ids = {role.id for role in SEED_ROLES}
    assert len(ids) == 4


@pytest.mark.unit
def test_seed_required_optional_affordance_sets_are_disjoint() -> None:
    """Decider enforces disjointness; seed must comply."""
    for role in SEED_ROLES:
        overlap = role.required_affordances & role.optional_affordances
        assert overlap == frozenset(), (
            f"Seed Role {role.name.value} has overlapping required + optional "
            f"Affordances: {sorted(a.value for a in overlap)}"
        )


@pytest.mark.unit
def test_imager_requires_imageable_affordance() -> None:
    assert "Imageable" in {a.value for a in IMAGER.required_affordances}


@pytest.mark.unit
def test_positioner_requires_homeable_and_limitable() -> None:
    names = {a.value for a in POSITIONER.required_affordances}
    assert "Homeable" in names
    assert "Limitable" in names


@pytest.mark.unit
def test_controller_required_affordances_non_empty() -> None:
    """<Domain>Controller pattern: the empty-Affordances leaf-Family
    role still requires at least one affordance at the Role-contract
    level (Identifiable). Distinguishes Controller from a degenerate
    tag-only Role (the Conditioner deferral reasoning per Q3)."""
    assert len(CONTROLLER.required_affordances) >= 1


@pytest.mark.unit
def test_detector_distinct_from_imager_required_set() -> None:
    """Detector requires Reportable; Imager requires Imageable. The
    distinction is the contract-level separation between scalar-reading
    point sensors and 2D frame imagers."""
    assert DETECTOR.required_affordances != IMAGER.required_affordances


@pytest.mark.unit
def test_no_seed_role_has_empty_required_affordances() -> None:
    """Per Q3 deferral: empty required_affordances degenerates a Role to a tag.

    Every shipped seed Role MUST have at least one required Affordance.
    Conditioner would have been empty; it was deferred for exactly this
    reason.
    """
    for role in SEED_ROLES:
        assert role.required_affordances != frozenset(), (
            f"Seed Role {role.name.value} has empty required_affordances; "
            "would be a degenerate tag-only Role. Defer or extend the "
            "contract before adding to the seed registry."
        )


@pytest.mark.unit
def test_no_seed_role_has_empty_docstring() -> None:
    for role in SEED_ROLES:
        assert role.docstring.strip(), (
            f"Seed Role {role.name.value} has empty / whitespace-only docstring"
        )
