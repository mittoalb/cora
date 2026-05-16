"""Aggregate kernels owned by the Campaign BC.

Campaign is a single-aggregate BC today (Campaign). The `aggregates`
sub-package exists so other BCs can target the aggregate kernel
specifically via `cora.campaign.aggregates` in `tach.toml`, while
`cora.campaign.features` stays implicitly off-limits to sibling BCs
per the cross-BC dependency contract.

This module is intentionally empty of re-exports: each aggregate
exposes its own surface via `cora.campaign.aggregates.<aggregate>`.
"""
