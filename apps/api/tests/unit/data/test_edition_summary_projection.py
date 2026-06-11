"""Static metadata tests for `EditionSummaryProjection`.

Per the projection-metadata-test convention: every projection-writer
subscription change requires updating the frozenset assertion here.
This test is the contract pin: it fails if the writer drops a
subscription or adds an unexpected one.
"""

from cora.data.projections.edition_summary import EditionSummaryProjection


def test_projection_metadata() -> None:
    proj = EditionSummaryProjection()
    assert proj.name == "proj_data_edition_summary"
    assert proj.subscribed_event_types == frozenset(
        {
            "EditionRegistered",
            "EditionDatasetAdded",
            "EditionDatasetRemoved",
            "EditionSealed",
            "EditionPublished",
            "EditionWithdrawn",
        }
    )
