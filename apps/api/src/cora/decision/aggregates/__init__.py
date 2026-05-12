"""Aggregates package for the Decision BC.

Each aggregate sits in a sibling subpackage with `state.py`, `events.py`,
`evolver.py`, `read.py` (plus `entries.py` for logbook-bearing aggregates).
Add a new aggregate by creating a new subpackage; this `__init__` is
intentionally empty so the package surface stays per-aggregate.
"""
