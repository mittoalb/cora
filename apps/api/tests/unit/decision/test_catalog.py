"""Smoke tests for the well-known decision_rule catalog.

Catalog is documented constants + naming convention; tests guard
against accidental string drift (renaming a constant value silently
breaks any operator who's already cited it).
"""

import pytest

from cora.decision import catalog


@pytest.mark.unit
def test_catalog_iso17025_simple_acceptance_value_locked() -> None:
    """The canonical ISO 17025 simple-acceptance citation string."""
    assert catalog.ISO17025_SIMPLE_ACCEPTANCE == "iso17025:7.1.3:simple_acceptance"


@pytest.mark.unit
def test_catalog_iso17025_guardband_value_locked() -> None:
    assert catalog.ISO17025_GUARDBAND == "iso17025:7.1.3:guardband"


@pytest.mark.unit
def test_catalog_iso17025_non_binary_value_locked() -> None:
    assert catalog.ISO17025_NON_BINARY == "iso17025:7.1.3:non_binary"


@pytest.mark.unit
def test_catalog_cora_internal_rules_follow_versioned_convention() -> None:
    """`cora:policy:<context>:<version>` shape per the catalog
    naming convention."""
    assert catalog.CORA_RECIPE_APPROVAL_V1 == "cora:policy:recipe_approval:v1"
    assert catalog.CORA_RUN_ABORT_V1 == "cora:policy:run_abort:v1"
    assert catalog.CORA_RUN_STOP_V1 == "cora:policy:run_stop:v1"
    assert catalog.CORA_RUN_TRUNCATE_V1 == "cora:policy:run_truncate:v1"
    assert catalog.CORA_DATASET_DISCARD_V1 == "cora:policy:dataset_discard:v1"


@pytest.mark.unit
def test_catalog_all_constants_are_unique() -> None:
    """No accidental duplicate values across the catalog."""
    values = [
        catalog.ISO17025_SIMPLE_ACCEPTANCE,
        catalog.ISO17025_GUARDBAND,
        catalog.ISO17025_NON_BINARY,
        catalog.CORA_RECIPE_APPROVAL_V1,
        catalog.CORA_RUN_ABORT_V1,
        catalog.CORA_RUN_STOP_V1,
        catalog.CORA_RUN_TRUNCATE_V1,
        catalog.CORA_DATASET_DISCARD_V1,
    ]
    assert len(values) == len(set(values))


@pytest.mark.unit
def test_catalog_all_export_list_matches_module_constants() -> None:
    """`__all__` should list every public constant; future
    additions get picked up by symbol-based importers."""
    public_attrs = {name for name in dir(catalog) if not name.startswith("_") and name.isupper()}
    assert public_attrs == set(catalog.__all__)
